import hashlib
import json
import math
import re
import time
from dataclasses import dataclass
from datetime import date, datetime
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.db import transaction

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
COORDINATES = {"latitude": 90, "longitude": 180}


class ImportFailure(ValueError):
    pass


@dataclass
class ParsedDataset:
    checksum: str
    offices: list
    duplicates: int
    source_date: date | None = None


@dataclass
class Snapshot:
    records: list
    source_date: date | None


def _get_json(url, *, attempts=4, timeout=60):
    """GET a JSON document, retrying transient gateway and network failures."""
    request = Request(url, headers={"Accept": "application/json", "User-Agent": "bharat"})
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


def parse_records(records, *, source_date=None):
    """Validate the entire snapshot before changing the active directory."""
    offices = {}
    duplicates = 0
    errors = []
    rejected = 0
    for number, record in enumerate(records, start=1):
        if not isinstance(record, dict):
            raw = {}
        else:
            raw = {re.sub(r"[\s_]", "", str(key)).lower(): value for key, value in record.items()}
        values = {field: str(raw.get(key) or "").strip() for key, field in FIELDS.items()}
        problem = None
        if missing := sorted(key for key in FIELDS if key not in raw):
            problem = f"missing fields: {', '.join(missing)}"
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
        if not problem and key in offices:
            if offices[key] != values:
                problem = "conflicting records for the same office identity"
            else:
                duplicates += 1
                continue
        if problem:
            rejected += 1
            if len(errors) < 10:
                errors.append(f"record {number}: {problem}")
        else:
            offices[key] = values
    if rejected:
        raise ImportFailure(f"Rejected {rejected} record(s); no data changed. " + "; ".join(errors))
    if not offices:
        raise ImportFailure("Snapshot contains no offices; refusing to replace the directory.")
    canonical = json.dumps(records, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return ParsedDataset(
        hashlib.sha256(canonical.encode()).hexdigest(),
        list(offices.values()),
        duplicates,
        source_date,
    )


@transaction.atomic
def replace_dataset(parsed, *, source):
    # SQLite's IMMEDIATE transactions (see settings) serialize concurrent imports.
    current, _ = Dataset.objects.get_or_create(pk=1, defaults={"source": source, "row_count": 0})
    if (current.checksum, current.source, current.source_date) == (
        parsed.checksum,
        source,
        parsed.source_date,
    ):
        return False
    PostOffice.objects.all().delete()
    PostOffice.objects.bulk_create(
        [PostOffice(**office) for office in parsed.offices], batch_size=1000
    )
    current.source = source
    current.source_date = parsed.source_date
    current.checksum = parsed.checksum
    current.row_count = len(parsed.offices)
    current.duplicate_count = parsed.duplicates
    current.save()
    return True
