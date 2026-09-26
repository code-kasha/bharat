# Working on Bharat

Bharat is a read-only Django REST Framework postal directory. Use Python 3.13 and uv.

## Commands

- Install: `uv sync --frozen`
- Check: `uv run ruff check .` and `uv run ruff format --check .`
- Tests: `uv run pytest`
- Migration drift: `uv run python manage.py makemigrations --check --dry-run`
- API contract: `uv run python manage.py spectacular --validate --fail-on-warn --file schema.yml`

## Boundaries and invariants

- `postal/importer.py` owns fetching, validation and transactional replacement; views never write data.
- Data comes only from the official data.gov.in API via `fetch_postal_data`. There are no CSV imports.
- A PIN is a six-character string and can map to many offices. Do not make PIN unique.
- Fully validate imports before mutation; failures must preserve the current data and metadata.
- Collapse exact duplicate rows, reject conflicting office identities, and report counts.
- Record source, optional source date, import timestamp and SHA256. Never invent data freshness.
- Tests use synthetic API-shaped fixtures and must never reach the network.
- Never commit API keys. Only the bundled `db.sqlite3` is tracked; it is the 2023 legacy snapshot
  (git f9ea722, provenance unverified, three repeated office identities kept as-is).
- Do not manually edit generated migrations or uv.lock. Generate and review them.
- SQLite is the only database, in development and deployment. Keep it on a persistent volume.
- Avoid unrelated frameworks, authentication, or a frontend build pipeline for this API milestone.
- Keep README examples and OpenAPI consistent with behavior. Add regression tests for fixes.
