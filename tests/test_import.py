import re
from datetime import date
from io import StringIO
from unittest.mock import patch

import pytest
from conftest import office
from django.core.management import call_command
from django.core.management.base import CommandError
from django.db import IntegrityError

from postal.importer import (
    ImportFailure,
    fetch_snapshot,
    parse_records,
    replace_dataset,
)
from postal.models import Dataset, PostOffice

pytestmark = pytest.mark.django_db


def pages(records, *, page_size=1, updated="2026-06-10T08:15:00Z"):
    """Fake data.gov.in pagination over synthetic records."""
    calls = []

    def get_json(url):
        calls.append(url)
        offset = int(url.split("offset=")[1].split("&")[0])
        return {
            "total": len(records),
            "updated_date": updated,
            "records": records[offset : offset + page_size],
        }

    get_json.calls = calls
    return get_json


def test_fetch_follows_pagination_and_reports_source_date(records):
    get_json = pages(records)
    snapshot = fetch_snapshot("key", "resource", page_size=1, get_json=get_json)
    assert snapshot.records == records
    assert snapshot.source_date == date(2026, 6, 10)
    assert len(get_json.calls) == 2
    assert "resource?api-key=key" in get_json.calls[0]


def test_fetch_without_updated_date_does_not_invent_one(records):
    snapshot = fetch_snapshot("k", get_json=pages(records, page_size=10, updated=None))
    assert snapshot.source_date is None


def test_truncated_download_is_rejected(records):
    def short(url):
        offset = int(url.split("offset=")[1].split("&")[0])
        return {"total": 5, "records": records if offset == 0 else []}

    with pytest.raises(ImportFailure, match="Received 2 of 5"):
        fetch_snapshot("k", get_json=short)


@pytest.mark.parametrize("response", [{"total": 1}, {"records": []}, ["unexpected"]])
def test_malformed_response_is_rejected(response):
    with pytest.raises(ImportFailure):
        fetch_snapshot("k", get_json=lambda url: response)


def test_import_preserves_multiple_offices_and_provenance(records):
    parsed = parse_records(records, source_date=date(2026, 6, 10))
    assert replace_dataset(parsed, source="fixture")
    assert PostOffice.objects.filter(pincode="400001").count() == 2
    dataset = Dataset.objects.get()
    assert dataset.source == "fixture"
    assert dataset.source_date == date(2026, 6, 10)
    assert dataset.checksum == parsed.checksum
    assert dataset.row_count == 2


def test_coordinates_are_kept_or_nulled_never_guessed(records):
    records.append(office("Office C", latitude="123.4", longitude="inf"))
    replace_dataset(parse_records(records), source="fixture")
    coordinates = dict(PostOffice.objects.values_list("office_name", "latitude"))
    assert coordinates == {"Office A": 18.93, "Office B": None, "Office C": None}


def test_repeat_import_does_not_change_ids_or_timestamp(records):
    parsed = parse_records(records)
    replace_dataset(parsed, source="fixture")
    ids = list(PostOffice.objects.values_list("pk", flat=True))
    timestamp = Dataset.objects.get().imported_at
    assert not replace_dataset(parse_records(records), source="fixture")
    assert list(PostOffice.objects.values_list("pk", flat=True)) == ids
    assert Dataset.objects.get().imported_at == timestamp


def test_replacement_removes_stale_offices(records):
    replace_dataset(parse_records(records), source="old")
    replace_dataset(parse_records(records[:1]), source="new")
    assert PostOffice.objects.count() == 1
    assert Dataset.objects.get().source == "new"


def test_failed_database_write_rolls_back_entire_snapshot(records):
    replace_dataset(parse_records(records), source="original")
    with patch("postal.importer.PostOffice.objects.bulk_create", side_effect=IntegrityError):
        with pytest.raises(IntegrityError):
            replace_dataset(parse_records(records[:1]), source="replacement")
    assert PostOffice.objects.count() == 2
    assert Dataset.objects.get().source == "original"


def test_exact_duplicates_are_counted():
    parsed = parse_records([office(), office()])
    assert len(parsed.offices) == 1
    assert parsed.duplicates == 1


def test_same_office_name_in_distinct_districts_is_preserved():
    assert len(parse_records([office(), office(district="Another District")]).offices) == 2


def test_field_names_are_normalized():
    record = {key.upper(): value for key, value in office().items()}
    assert parse_records([record]).offices[0]["office_name"] == "Office A"


def test_repeated_office_identities_are_kept_and_counted():
    records = [
        office(),
        office(delivery="Non Delivery"),
        office(name="OFFICE A", officetype="SO"),  # identity is case-insensitive
        office(),  # exact repeat of the first row: merged
        office("Office B"),
    ]
    parsed = parse_records(records)
    assert [row["delivery"] for row in parsed.offices[:2]] == ["Delivery", "Non Delivery"]
    assert (len(parsed.offices), parsed.duplicates, parsed.repeated_identities) == (4, 1, 1)
    replace_dataset(parsed, source="fixture")
    dataset = Dataset.objects.get()
    assert (dataset.row_count, dataset.repeated_identity_count) == (4, 1)


@pytest.mark.parametrize("pin", ["012345", "12345", "1234567", "abcdef", "४००००१", None])
def test_invalid_pin_rejects_snapshot(pin):
    with pytest.raises(ImportFailure, match="Rejected 1"):
        parse_records([office(pincode=pin)])


def test_missing_field_rejects_snapshot():
    record = office()
    del record["statename"]
    with pytest.raises(ImportFailure, match="missing fields: statename"):
        parse_records([record, "not a record"])


def test_empty_snapshot_refused():
    with pytest.raises(ImportFailure, match="no offices"):
        parse_records([])


def test_command_requires_api_key(monkeypatch):
    monkeypatch.delenv("DATA_GOV_IN_API_KEY", raising=False)
    with pytest.raises(CommandError, match="DATA_GOV_IN_API_KEY"):
        call_command("fetch_postal_data")


def test_command_imports_with_official_source(monkeypatch, records):
    monkeypatch.setenv("DATA_GOV_IN_API_KEY", "secret")
    output = StringIO()
    with patch("postal.importer._get_json", pages(records, page_size=1000)):
        call_command("fetch_postal_data", stdout=output)
    dataset = Dataset.objects.get()
    assert dataset.source == "https://api.data.gov.in/resource/5c2f62fe-5afa-4119-a499-fec9d604d5bd"
    assert dataset.source_date == date(2026, 6, 10)
    assert "secret" not in dataset.source + output.getvalue()
    assert "Imported: 2 offices" in output.getvalue()


def test_dry_run_does_not_write(monkeypatch, records):
    monkeypatch.setenv("DATA_GOV_IN_API_KEY", "k")
    output = StringIO()
    with patch("postal.importer._get_json", pages(records)):
        call_command("fetch_postal_data", dry_run=True, stdout=output)
    assert "dry run" in output.getvalue()
    assert not Dataset.objects.exists()
    assert not PostOffice.objects.exists()


def test_bad_download_preserves_existing_directory(monkeypatch, records):
    replace_dataset(parse_records(records), source="original")
    monkeypatch.setenv("DATA_GOV_IN_API_KEY", "k")
    with patch("postal.importer._get_json", pages([office(pincode="bad")])):
        with pytest.raises(CommandError, match="Rejected 1"):
            call_command("fetch_postal_data")
    assert PostOffice.objects.count() == 2
    assert Dataset.objects.get().source == "original"


def test_http_errors_become_import_failures():
    from urllib.error import HTTPError

    from postal.importer import _get_json

    error = HTTPError("https://example.invalid", 403, "Forbidden", {}, None)
    with patch("postal.importer.urlopen", side_effect=error):
        with pytest.raises(ImportFailure, match="HTTP 403"):
            _get_json("https://example.invalid")


def test_transient_gateway_errors_are_retried():
    from io import BytesIO
    from urllib.error import HTTPError

    from postal.importer import _get_json

    error = HTTPError("https://example.invalid", 502, "Bad Gateway", {}, None)
    with (
        patch("postal.importer.urlopen", side_effect=[error, BytesIO(b'{"ok": 1}')]),
        patch("postal.importer.time.sleep") as sleep,
    ):
        assert _get_json("https://example.invalid") == {"ok": 1}
    sleep.assert_called_once()


@pytest.mark.django_db(transaction=True)
def test_replacement_checkpoints_the_write_ahead_log(records):
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    with CaptureQueriesContext(connection) as queries:
        replace_dataset(parse_records(records), source="fixture")
    assert "PRAGMA wal_checkpoint(TRUNCATE)" in queries[-1]["sql"]


def test_migration_counts_repeated_offices_in_an_existing_directory(records):
    from importlib import import_module
    from types import SimpleNamespace

    from django.apps import apps
    from django.db import connection

    replace_dataset(parse_records(records + [office(delivery="Non Delivery")]), source="old")
    Dataset.objects.update(repeated_identity_count=0)
    migration = import_module("postal.migrations.0006_count_repeated_identities")
    migration.count_repeated_identities(apps, SimpleNamespace(connection=connection))
    assert Dataset.objects.get().repeated_identity_count == 1


def bharat_office(name="Office A", **overrides):
    """An office as Bharat's export and API write it."""
    return {
        "pincode": "400001",
        "office_name": name,
        "district": "District",
        "state": "State",
        "circle": "Circle",
        "region": "",
        "division": "Division",
        "office_type": "HO",
        "delivery": "Delivery",
        "latitude": None,
        "longitude": 72.83,
    } | overrides


def as_json(document):
    import json

    return json.dumps(document).encode()


def test_json_bharat_export_carries_its_provenance():
    from postal.importer import parse_upload

    raw = as_json(
        {
            "dataset": {"source": "Bharat mirror", "source_date": "2025-06-30", "row_count": 2},
            "offices": [bharat_office(), bharat_office("Office B")],
        }
    )
    parsed, carried = parse_upload(raw)
    assert carried == {"source": "Bharat mirror", "source_date": date(2025, 6, 30)}
    assert [row["office_name"] for row in parsed.offices] == ["Office A", "Office B"]
    assert parsed.offices[0]["state"] == "State" and parsed.offices[0]["region"] == ""
    assert (parsed.offices[0]["latitude"], parsed.offices[0]["longitude"]) == (None, 72.83)
    import hashlib

    assert parsed.checksum == hashlib.sha256(raw).hexdigest()


def test_json_data_gov_in_response_and_plain_lists():
    from postal.importer import parse_upload

    response = {"total": 2, "records": [office(), office("Office B", pincode=400002)]}
    parsed, carried = parse_upload(as_json(response))
    assert carried == {} and parsed.offices[1]["pincode"] == "400002"
    csv_names = {
        "Circle Name": "C",
        "Region Name": "R",
        "Division Name": "D",
        "Office Name": "Listed",
        "Pincode": "560001",
        "OfficeType": "HO",
        "Delivery": "Delivery",
        "District": "Bengaluru",
        "StateName": "Karnataka",
    }
    for records in ([csv_names], [bharat_office("Listed")]):
        parsed, carried = parse_upload(b"\n  " + as_json(records))
        assert carried == {} and parsed.offices[0]["office_name"] == "Listed"


@pytest.mark.parametrize(
    "raw,message",
    [
        (b'{"offices": [', "not valid JSON: Expecting value at line 1, column 14"),
        (b'{"rows": []}', "Unrecognized JSON"),
        (b"[]", "no offices"),
        (as_json([bharat_office(), bharat_office(pincode="0123")]), "record 2: PIN must"),
        (as_json({"records": [office(), "x"]}), "record 2: missing fields"),
        (as_json([bharat_office(state=["A"])]), "record 1: fields must be text"),
    ],
)
def test_bad_json_is_explained(raw, message):
    from postal.importer import parse_upload

    with pytest.raises(ImportFailure, match=re.escape(message)):
        parse_upload(raw)
