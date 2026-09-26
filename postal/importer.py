import csv
import hashlib
import io
import json
import math
import re
import time
from dataclasses import dataclass
from datetime import date, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.db import DEFAULT_DB_ALIAS, connections, transaction

from postal.models import Dataset, PostOffice

API_ROOT = "https://api.data.gov.in/resource/"
# Department of Posts, "All India Pincode Directory till last month" on data.gov.in.
DEFAULT_RESOURCE = "5c2f62fe-5afa-4119-a499-fec9d604d5bd"

FIELDS = {
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
# bharat-post-dir's own field names (the export and API), normalized like the keys above.
ALIASES = {
    "state": "statename",
    "circle": "circlename",
    "region": "regionname",
    "division": "divisionname",
}
COORDINATES = {"latitude": 90, "longitude": 180}


class ImportFailure(ValueError):
    pass


@dataclass
class ParsedDataset:
    checksum: str
    offices: list
    duplicates: int
    source_date: date | None = None
    # Offices (same PIN, state, district and name) listed more than once with different details.
    repeated_identities: int = 0


@dataclass
class Snapshot:
    records: list
    source_date: date | None


def _get_json(url, *, attempts=4, timeout=60):
    """GET a JSON document, retrying transient gateway and network failures."""
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "bharat-post-dir"})
    for attempt in range(1, attempts + 1):
        try:
            with urlopen(request, timeout=timeout) as response:
                return json.load(response)
        except HTTPError as exc:
            if (exc.code < 500 and exc.code != 429) or attempt == attempts:
                raise ImportFailure(f"data.gov.in returned HTTP {exc.code}.") from exc
        except (URLError, TimeoutError) as exc:
            if attempt == attempts:
                raise ImportFailure(f"Could not reach data.gov.in: {exc}") from exc
        time.sleep(2**attempt)


def _source_date(value):
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00")).date()
    except ValueError:
        return None


def fetch_snapshot(api_key, resource=DEFAULT_RESOURCE, *, page_size=1000, get_json=None):
    """Download every record of an OGD resource; nothing is written here."""
    get_json = get_json or _get_json
    records = []
    total = None
    source_date = None
    while total is None or len(records) < total:
        query = urlencode(
            {"api-key": api_key, "format": "json", "offset": len(records), "limit": page_size}
        )
        page = get_json(f"{API_ROOT}{resource}?{query}")
        if not isinstance(page, dict) or not isinstance(page.get("records"), list):
            raise ImportFailure("Unexpected response from data.gov.in (no records list).")
        if total is None:
            try:
                total = int(page["total"])
            except (KeyError, TypeError, ValueError) as exc:
                raise ImportFailure("data.gov.in response did not report a total.") from exc
            source_date = _source_date(page.get("updated_date"))
        if not page["records"]:
            break
        records.extend(page["records"])
    if len(records) != total:
        raise ImportFailure(f"Received {len(records)} of {total} records; no data changed.")
    return Snapshot(records, source_date)


def _coordinate(value, limit):
    try:
        number = float(str(value).strip())
    except ValueError:
        return None
    return number if math.isfinite(number) and -limit <= number <= limit else None


def parse_records(records, *, source_date=None, position="record {}".format):
    """Validate the entire snapshot before changing the active directory.

    Exact repeated rows are merged. Differing rows for the same office identity are all kept:
    government data can list an office twice legitimately, so they are counted, not rejected.
    """
    offices = []
    variants = {}
    duplicates = 0
    errors = []
    rejected = 0
    for number, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raw = {}
        else:
            raw = {re.sub(r"[\s_]", "", str(key)).lower(): value for key, value in record.items()}
            for alias, key in ALIASES.items():
                if alias in raw and key not in raw:
                    raw[key] = raw.pop(alias)
        values = {field: str(raw.get(key) or "").strip() for key, field in FIELDS.items()}
        problem = None
        if missing := sorted(key for key in FIELDS if key not in raw):
            problem = f"missing fields: {', '.join(missing)}"
        elif nested := sorted(key for key in FIELDS if isinstance(raw[key], dict | list)):
            problem = f"fields must be text, not lists or objects: {', '.join(nested)}"
        elif not re.fullmatch(r"[1-9][0-9]{5}", values["pincode"]):
            problem = "PIN must contain six digits and cannot start with zero"
        else:
            for field, value in values.items():
                limit = PostOffice._meta.get_field(field).max_length
                if (not value and field != "region") or len(value) > limit:
                    problem = f"invalid or empty {field} (maximum {limit} characters)"
                    break
        values |= {name: _coordinate(raw.get(name), limit) for name, limit in COORDINATES.items()}
        key = tuple(
            values[field].casefold() for field in ("pincode", "state", "district", "office_name")
        )
        if problem:
            rejected += 1
            if len(errors) < 10:
                errors.append(f"{position(number)}: {problem}")
            continue
        seen = variants.setdefault(key, [])
        if values in seen:
            duplicates += 1
            continue
        seen.append(values)
        offices.append(values)
    if rejected:
        raise ImportFailure(f"Rejected {rejected} record(s); no data changed. " + "; ".join(errors))
    if not offices:
        raise ImportFailure("Snapshot contains no offices; refusing to replace the directory.")
    canonical = json.dumps(records, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return ParsedDataset(
        hashlib.sha256(canonical.encode()).hexdigest(),
        offices,
        duplicates,
        source_date,
        sum(len(seen) > 1 for seen in variants.values()),
    )


def _decode(raw):
    try:
        return raw.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        message = "The file is not UTF-8 text. Save it as CSV UTF-8 (or UTF-8 JSON) and try again."
        raise ImportFailure(message) from exc


def _finish(parsed, raw):
    # Record the file's own hash so users can check it with any SHA256 tool.
    parsed.checksum = hashlib.sha256(raw).hexdigest()
    return parsed


def _parse_csv_text(text, raw):
    try:
        reader = csv.DictReader(io.StringIO(text, newline=""))
        rows = []
        for row in reader:
            if None in row or None in row.values():
                raise ImportFailure(
                    f"Line {reader.line_num} has a different number of fields than the header; "
                    "no data changed."
                )
            rows.append(row)
    except csv.Error as exc:
        raise ImportFailure(f"The file is not valid CSV: {exc}") from exc
    # Line 1 is the header, so record N is on line N + 1 of the file.
    return _finish(parse_records(rows, position=lambda number: f"line {number + 1}"), raw)


def parse_csv(raw):
    """Validate an uploaded CSV (the directory's column layout) without writing anything."""
    return _parse_csv_text(_decode(raw), raw)


JSON_SHAPES = (
    'bharat-post-dir\'s export ({"dataset": ..., "offices": [...]}), a data.gov.in response '
    '({"records": [...]}) or a list of offices'
)


def _export_details(dataset):
    """Provenance carried by a bharat-post-dir export, for form fields left empty."""
    if not isinstance(dataset, dict):
        return {}
    details = {}
    for field in ("source", "source_period"):
        if isinstance(dataset.get(field), str) and dataset[field].strip():
            details[field] = dataset[field].strip()
    if isinstance(dataset.get("source_date"), str):
        try:
            details["source_date"] = date.fromisoformat(dataset["source_date"])
        except ValueError:
            pass
    return details


def parse_json(raw, text=None):
    """Validate an uploaded JSON file in any accepted shape; returns (parsed, export details)."""
    try:
        document = json.loads(_decode(raw) if text is None else text)
    except json.JSONDecodeError as exc:
        raise ImportFailure(
            f"The file is not valid JSON: {exc.msg} at line {exc.lineno}, column {exc.colno}."
        ) from exc
    details = {}
    if isinstance(document, list):
        records = document
    elif isinstance(document, dict) and isinstance(document.get("offices"), list):
        records = document["offices"]
        details = _export_details(document.get("dataset"))
    elif isinstance(document, dict) and isinstance(document.get("records"), list):
        records = document["records"]
    else:
        raise ImportFailure(f"Unrecognized JSON. Upload {JSON_SHAPES}.")
    return _finish(parse_records(records), raw), details


def parse_upload(raw):
    """Validate an uploaded CSV or JSON file, detected from its content, without writing.

    Returns the parsed dataset and any provenance the file itself carries (an export).
    """
    text = _decode(raw)
    if text.lstrip()[:1] in ("{", "["):
        return parse_json(raw, text)
    return _parse_csv_text(text, raw), {}


def replace_dataset(parsed, *, source, source_period="", using=DEFAULT_DB_ALIAS):
    """Swap in a validated dataset; `using` also targets a temporary upload's own database."""
    # SQLite's IMMEDIATE transactions (see settings) serialize concurrent imports.
    with transaction.atomic(using=using):
        current, _ = Dataset.objects.db_manager(using).get_or_create(
            pk=1, defaults={"source": source, "row_count": 0}
        )
        if (current.checksum, current.source, current.source_date, current.source_period) == (
            parsed.checksum,
            source,
            parsed.source_date,
            source_period,
        ):
            return False
        offices = PostOffice.objects.db_manager(using)
        offices.all().delete()
        offices.bulk_create([PostOffice(**office) for office in parsed.offices], batch_size=1000)
        current.source = source
        current.source_date = parsed.source_date
        current.source_period = source_period
        current.checksum = parsed.checksum
        current.row_count = len(parsed.offices)
        current.duplicate_count = parsed.duplicates
        current.repeated_identity_count = parsed.repeated_identities
        current.save(using=using)
    # Fold the write-ahead log into the database file, so the file alone (for example a
    # committed db.sqlite3) holds the new directory. SQLite cannot do this mid-transaction.
    connection = connections[using]
    if not connection.in_atomic_block:
        with connection.cursor() as cursor:
            cursor.execute("PRAGMA wal_checkpoint(TRUNCATE)")
    return True
