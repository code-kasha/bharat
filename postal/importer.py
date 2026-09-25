import csv
import hashlib
import io
import re
from dataclasses import dataclass
from pathlib import Path

from django.db import transaction

from postal.models import Dataset, PostOffice

HEADERS = {
    "circlename": "circle",
    "regionname": "region",
    "divisionname": "division",
    "officename": "office_name",
    "pincode": "pincode",
    "officetype": "office_type",
    "delivery": "delivery",
    "district": "district",
    "statename": "state",
}


class ImportFailure(ValueError):
    pass


@dataclass
class ParsedDataset:
    checksum: str
    offices: list
    duplicates: int


def parse_csv(path):
    """Validate the entire file before changing the active directory."""
    raw = Path(path).read_bytes()
    reader = csv.DictReader(io.StringIO(raw.decode("utf-8-sig"), newline=""))
    original = reader.fieldnames or []
    normalized = [re.sub(r"[\s_]", "", name).lower() for name in original]
    if len(set(normalized)) != len(normalized):
        raise ImportFailure("Duplicate CSV column names.")
    missing = set(HEADERS) - set(normalized)
    if missing:
        raise ImportFailure(f"Missing required columns: {', '.join(sorted(missing))}")
    mapping = dict(zip(original, normalized, strict=True))
    records = {}
    duplicates = 0
    errors = []
    rejected = 0
    for row in reader:
        values = {
            HEADERS[mapping[key]]: (value or "").strip()
            for key, value in row.items()
            if key in mapping and mapping[key] in HEADERS
        }
        problem = None
        if None in row or any(value is None for value in row.values()):
            problem = "row has a different number of fields than the header"
        elif not re.fullmatch(r"[1-9][0-9]{5}", values["pincode"]):
            problem = "PIN must contain six digits and cannot start with zero"
        else:
            for field, value in values.items():
                limit = PostOffice._meta.get_field(field).max_length
                if (not value and field != "region") or len(value) > limit:
                    problem = f"invalid or empty {field} (maximum {limit} characters)"
                    break
        key = tuple(
            values[field].casefold() for field in ("pincode", "state", "district", "office_name")
        )
        if not problem and key in records:
            if records[key] != values:
                problem = "conflicting records for the same office identity"
            else:
                duplicates += 1
                continue
        if problem:
            rejected += 1
            if len(errors) < 10:
                errors.append(f"line {reader.line_num}: {problem}")
        else:
            records[key] = values
    if rejected:
        raise ImportFailure(f"Rejected {rejected} row(s); no data changed. " + "; ".join(errors))
    if not records:
        raise ImportFailure("CSV contains no offices; refusing to replace the directory.")
    return ParsedDataset(hashlib.sha256(raw).hexdigest(), list(records.values()), duplicates)


@transaction.atomic
def replace_dataset(parsed, *, source, source_date=None):
    # The singleton row serializes imports on PostgreSQL, including the first import.
    Dataset.objects.get_or_create(pk=1, defaults={"source": source, "row_count": 0})
    current = Dataset.objects.select_for_update().get(pk=1)
    if (current.checksum, current.source, current.source_date) == (
        parsed.checksum,
        source,
        source_date,
    ):
        return False
    PostOffice.objects.all().delete()
    PostOffice.objects.bulk_create(
        [PostOffice(**office) for office in parsed.offices], batch_size=1000
    )
    current.source = source
    current.source_date = source_date
    current.checksum = parsed.checksum
    current.row_count = len(parsed.offices)
    current.duplicate_count = parsed.duplicates
    current.save()
    return True
