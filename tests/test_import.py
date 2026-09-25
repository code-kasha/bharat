from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError

from postal.importer import ImportFailure, parse_csv, replace_dataset
from postal.models import Dataset, PostOffice

pytestmark = pytest.mark.django_db


def test_import_preserves_multiple_offices_and_provenance(csv_file):
    parsed = parse_csv(csv_file())
    assert replace_dataset(parsed, source="fixture")
    assert PostOffice.objects.filter(pincode="400001").count() == 2
    dataset = Dataset.objects.get()
    assert dataset.source == "fixture"
    assert dataset.source_date is None
    assert dataset.checksum == parsed.checksum
    assert dataset.row_count == 2


def test_repeat_import_does_not_change_ids_or_timestamp(csv_file):
    parsed = parse_csv(csv_file())
    replace_dataset(parsed, source="fixture")
    ids = list(PostOffice.objects.values_list("pk", flat=True))
    timestamp = Dataset.objects.get().imported_at
    assert not replace_dataset(parsed, source="fixture")
    assert list(PostOffice.objects.values_list("pk", flat=True)) == ids
    assert Dataset.objects.get().imported_at == timestamp


def test_replacement_removes_stale_offices(csv_file):
    parsed = parse_csv(csv_file())
    replace_dataset(parsed, source="old")
    parsed.offices = parsed.offices[:1]
    parsed.checksum = "a" * 64
    replace_dataset(parsed, source="new")
    assert PostOffice.objects.count() == 1
    assert Dataset.objects.get().source == "new"


def test_failed_database_write_rolls_back_entire_snapshot(csv_file):
    parsed = parse_csv(csv_file())
    replace_dataset(parsed, source="original")
    with patch("postal.importer.PostOffice.objects.bulk_create", side_effect=IntegrityError):
        with pytest.raises(IntegrityError):
            replace_dataset(parsed, source="replacement")
    assert PostOffice.objects.count() == 2
    assert Dataset.objects.get().source == "original"


def test_exact_duplicates_are_counted(csv_file):
    row = ["C", "R", "D", "Office", "400001", "HO", "Delivery", "District", "State"]
    parsed = parse_csv(csv_file([row, row]))
    assert len(parsed.offices) == 1
    assert parsed.duplicates == 1


def test_same_office_name_in_distinct_districts_is_preserved(csv_file):
    row = ["C", "R", "D", "Office", "400001", "HO", "Delivery", "District", "State"]
    other = row.copy()
    other[7] = "Another District"
    assert len(parse_csv(csv_file([row, other])).offices) == 2


def test_spaced_headers_are_supported():
    from pathlib import Path

    sample = Path(__file__).resolve().parent.parent / "data" / "sample.csv"
    assert len(parse_csv(sample).offices) == 3


def test_conflicting_duplicates_are_rejected(csv_file):
    row = ["C", "R", "D", "Office", "400001", "HO", "Delivery", "District", "State"]
    conflicting = row.copy()
    conflicting[6] = "Non-Delivery"
    with pytest.raises(ImportFailure, match="conflicting"):
        parse_csv(csv_file([row, conflicting]))


@pytest.mark.parametrize("pin", ["012345", "12345", "1234567", "abcdef", "४००००१"])
def test_invalid_pin_rejects_snapshot(csv_file, pin):
    with pytest.raises(ImportFailure, match="Rejected 1"):
        parse_csv(csv_file([["C", "R", "D", "Office", pin, "HO", "Delivery", "District", "State"]]))


def test_missing_header(csv_file):
    with pytest.raises(ImportFailure, match="Missing required"):
        parse_csv(csv_file([], ["Pincode"]))


def test_empty_snapshot_refused(csv_file):
    with pytest.raises(ImportFailure, match="no offices"):
        parse_csv(csv_file([]))


def test_short_row_reports_validation_error(csv_file):
    with pytest.raises(ImportFailure, match="different number"):
        parse_csv(csv_file([["C"]]))


def test_dry_run_does_not_write(csv_file):
    output = StringIO()
    call_command(
        "import_postal_data", str(csv_file()), source="fixture", dry_run=True, stdout=output
    )
    assert "dry run" in output.getvalue()
    assert not Dataset.objects.exists()
    assert not PostOffice.objects.exists()


def test_bad_import_preserves_existing_directory(csv_file):
    replace_dataset(parse_csv(csv_file()), source="original")
    with pytest.raises(CommandError):
        call_command("import_postal_data", str(csv_file([])), source="bad")
    assert PostOffice.objects.count() == 2
    assert Dataset.objects.get().source == "original"
