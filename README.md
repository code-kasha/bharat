# Bharat

An Indian postal directory API built with Django REST Framework. Look up the offices associated with a PIN, search by office or district, and inspect where the imported data came from.

**Status:** first API milestone. Local demo data is synthetic. No hosted deployment or verified current postal dataset is included yet. A PIN may map to multiple offices; this service does not verify that a street address is deliverable.

## Quick start

Requires Python 3.13 and [uv](https://docs.astral.sh/uv/). SQLite works locally; deployment uses PostgreSQL.

```sh
uv sync --frozen
uv run python manage.py migrate
uv run python manage.py import_postal_data data/sample.csv --source "Synthetic demonstration data"
uv run python manage.py runserver
```

Open [API documentation](http://127.0.0.1:8000/api/docs/) or [a sample PIN lookup](http://127.0.0.1:8000/api/v1/pincodes/400001/). The sample's office names and locations are fictional.

## API

All data endpoints are read-only and public. Writes happen only through the local management command.

| Endpoint | Behavior |
| --- | --- |
| `GET /api/v1/pincodes/400001/` | Matching offices, paginated; malformed PIN is 400, absent PIN is 404 |
| `GET /api/v1/offices/?search=market` | Search office names and districts |
| `GET /api/v1/offices/?state=Example%20State&district=Example%20District` | Case-insensitive exact filters; combine with search or pincode |
| `GET /api/v1/dataset/` | Source, optional source date, SHA256, import timestamp and counts; 404 before first import |
| `GET /api/schema/` | Generated OpenAPI schema |
| `GET /api/docs/` | Interactive Swagger documentation (UI assets loaded from a CDN) |
| `GET /health/` | Process/database connectivity; does not assert dataset freshness |

Lists return `count`, `next`, `previous`, and `results`, with 25 offices per page. Follow `next` to retrieve further matches. Search requires 2–100 characters. An empty list is valid when filters match nothing or before an import.

```json
{
  "count": 2,
  "next": null,
  "previous": null,
  "results": [
    {
      "pincode": "400001",
      "office_name": "Example Central Office",
      "district": "Example District",
      "state": "Example State",
      "circle": "Demo Circle",
      "region": "Demo Region",
      "division": "Demo Division",
      "office_type": "HO",
      "delivery": "Delivery"
    }
  ]
}
```

Example above abbreviates the results array; the real sample lookup returns both offices.

## Importing a dataset

```sh
uv run python manage.py import_postal_data path/to/postal.csv --source "Source URL or provenance label" --dry-run
uv run python manage.py import_postal_data path/to/postal.csv --source "Source URL or provenance label" --source-date 2026-09-01
```

Supply the source date only when it is known; the date above is an example, not a claim about the bundled file. Run one import process at a time in local SQLite development.

The CSV must contain Circle Name, Region Name, Division Name, Office Name, Pincode, OfficeType, Delivery, District and StateName. Header matching ignores spaces, underscores and case. UTF-8 with or without a BOM is supported. Additional columns are ignored; malformed row widths are rejected. Region may be empty; the other fields may not.

The importer validates the complete file before writing. It preserves six-digit PINs as strings, collapses identical records, rejects conflicting identities, and refuses empty snapshots. Office identity is PIN + state + district + office name (case-insensitive during import). A failed import leaves the current directory untouched. Successful imports replace the entire directory and metadata in one transaction. Repeating the same bytes and provenance is a no-op. Database-generated IDs are deliberately not exposed as stable public identifiers.

Imports are serialized through a singleton metadata row on PostgreSQL. The importer currently holds the parsed snapshot in memory; very large or frequent imports would warrant staging tables. Pagination is deterministic within a snapshot, not pinned across concurrent replacements.

### Bundled legacy CSV

`data/input.csv` is preserved from the original project. Its upstream origin, date and redistribution terms have not been verified. Do not advertise it as current or complete. Validation currently rejects three conflicting identities at CSV lines **59179, 83789 and 91853**. Resolve these against an authoritative source rather than discarding records arbitrarily. `data/sample.csv` is the supported reproducible demo.

The [official data.gov.in directory](https://www.data.gov.in/resource/all-india-pincode-directory-till-last-month) is a candidate for a future verified snapshot. Download, review its schema and terms, and record provenance before importing. The service does not currently fetch or refresh external data automatically.

## Architecture

- `config/`: settings, URL routing, WSGI entrypoint.
- `postal/models.py`: current dataset metadata and indexed office records.
- `postal/importer.py`: parsing, validation, duplicate detection and atomic replacement.
- `postal/management/commands/`: operator-only import entrypoint.
- `postal/serializers.py` and `views.py`: validation, read-only API and generated schema.
- `tests/`: synthetic fixtures, rollback/import regressions, API behavior.
- `app.py` and `tools/`: original interactive export CLI, retained for compatibility.

The design deliberately starts with one directory snapshot, no user accounts, and no external runtime data provider. PIN lookup uses an indexed exact match. Place search uses substring matching; it is not fuzzy search and has not been benchmarked at production traffic levels. Django 5.2 is an [LTS release](https://docs.djangoproject.com/en/5.2/releases/5.2/).

## Configuration

Environment variables are read by Django. `.env` files are not automatically loaded by Django; use `uv run --env-file .env ...` if you create one from `.env.example`.

| Variable | Local default / purpose |
| --- | --- |
| `DJANGO_DEBUG` | `true`; must be `false` on a public deployment |
| `DJANGO_SECRET_KEY` | Development-only fallback; provide a generated secret in production |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1]`; comma-separated hostnames |
| `DATABASE_URL` | Local SQLite fallback; PostgreSQL URL required with debug disabled |
| `TRUST_PROXY_HTTPS` | `false`; enable only behind a trusted TLS proxy that strips incoming forwarding headers |

## Validation

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py spectacular --validate --fail-on-warn --file schema.yml
```

Tests cover one-to-many PIN lookup, input validation, filters, pagination, read-only routes, provenance, duplicate/conflict handling, idempotence, dry runs and rollback. Set `DATABASE_URL` to a disposable PostgreSQL database to run on the production database engine. Pytest creates a separate test database; the role needs permission to create it. Never point tests at production.

## CI and release delivery

GitHub Actions installs the frozen lockfile, checks formatting/lint, runs tests against PostgreSQL 17, validates migrations/OpenAPI, exercises sample import and builds the container. A `v*` Git tag publishes a versioned image to `ghcr.io/<owner>/<repository>` only after these checks pass. No image has been published by this local work.

The Docker image uses Gunicorn and an unprivileged user. It excludes the bundled CSV and local environment files. Build with `docker build -t bharat:local .`.

For a hosted release:

1. Provision PostgreSQL and TLS ingress; set the production environment variables above.
2. Deploy the verified versioned image. Configure forwarding-header trust only for your actual proxy setup.
3. Back up the database, then execute `/app/.venv/bin/python manage.py migrate --noinput` as a release task before routing traffic.
4. Mount a verified CSV into a one-off container and run the import command with its provenance. Do not rebuild the image to change the dataset.
5. Check `/health/`, dataset metadata and a known PIN lookup over HTTPS. Apply request limits at the ingress for a public demo.
6. Retain the previous image digest. Roll back application code only when schema-compatible; otherwise restore the matching database backup. Re-import a retained prior CSV to roll back a dataset.

Hosting-specific automatic deployment is pending selection of the host and domain. The workflow provides tested image delivery, not an already-live service.

## Next milestones

- Resolve dataset provenance and conflicting records; add a documented refresh process.
- Add a small accessible lookup interface with source/freshness labels.
- Add versioned data exports and measure query/import performance on a verified full snapshot.
- Connect the release image to the selected hosting platform and verify deployment rollback.

The original manifest declared MIT, but no license file was present. Confirm the intended code license before publishing a license file; data licensing is a separate decision.
