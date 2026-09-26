# Working on Bharat

Bharat is a read-only Django REST Framework postal directory. Use Python 3.13 and uv.

## Commands

- Install: `uv sync --frozen`
- Check: `uv run ruff check .` and `uv run ruff format --check .`
- Tests: `uv run pytest`
- Migration drift: `uv run python manage.py makemigrations --check --dry-run`
- API contract: `uv run python manage.py spectacular --validate --fail-on-warn --file schema.yml`

## Boundaries and invariants

- `postal/importer.py` owns fetching, CSV parsing, validation and transactional replacement. The only
  writers are `fetch_postal_data` and the local change-source page (`/source/`), both through the importer.
- The change-source page has no authentication: keep it local-only and CSRF-protected. It is on in a clone
  and off in the Docker image and on hosted sites (`BHARAT_ALLOW_SOURCE_CHANGE=false`). With `DEBUG` it
  replaces the database; otherwise `postal/uploads.py` keeps the upload in a scratch SQLite file that only
  the uploading browser's lookup page reads. The API and export always serve the default dataset. No CSV
  files are stored in the repository.
- A PIN is a six-character string and can map to many offices. Do not make PIN unique.
- Fully validate imports before mutation; failures must preserve the current data and metadata.
- Collapse exact duplicate rows, keep every differing row for a repeated office identity (government
  data can list an office twice legitimately), and report both counts.
- Record source, optional source date, import timestamp and SHA256. Never invent data freshness.
- Tests use synthetic API-shaped fixtures and must never reach the network.
- Never commit API keys. Only the bundled `db.sqlite3` is tracked: the maintainer-verified 2023
  snapshot (git f9ea722), with three repeated office identities kept as-is. Do not alter its rows.
- The Docker image bundles `db.sqlite3` and must run locally with no extra setup; hosting is out of scope.
- The lookup page (`/`) must cost one HTTP request: inline CSS only, no JavaScript or external assets.
- `/api/v1/export/` must deliver the whole directory in one streamed request; never paginate it.
- Do not manually edit generated migrations or uv.lock. Generate and review them.
- SQLite is the only database, in development and deployment. Keep it on a persistent volume.
- Avoid unrelated frameworks, authentication, or a frontend build pipeline for this API milestone.
- Keep README examples and OpenAPI consistent with behavior. Add regression tests for fixes.

## Ongoing work

The remaining work, settled decisions and how to resume are in `TODO.md`. Read it before starting.
