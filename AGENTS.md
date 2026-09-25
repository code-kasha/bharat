# Working on Bharat

Bharat is a read-only Django REST Framework postal directory. Use Python 3.13 and uv.

## Commands

- Install: `uv sync --frozen`
- Check: `uv run ruff check .` and `uv run ruff format --check .`
- Tests: `uv run pytest`
- Migration drift: `uv run python manage.py makemigrations --check --dry-run`
- API contract: `uv run python manage.py spectacular --validate --fail-on-warn --file schema.yml`

## Boundaries and invariants

- `postal/importer.py` owns validation and transactional replacement; views never write data.
- A PIN is a six-character string and can map to many offices. Do not make PIN unique.
- Fully validate imports before mutation; failures must preserve the current data and metadata.
- Collapse exact duplicate rows, reject conflicting office identities, and report counts.
- Record source, optional source date, import timestamp and SHA256. Never invent data freshness.
- `data/input.csv` is a legacy snapshot of unverified provenance; do not silently rewrite it.
- `data/sample.csv` is explicitly synthetic. Tests use synthetic temporary fixtures.
- Do not manually edit generated migrations or uv.lock. Generate and review them.
- PostgreSQL is the deployment target. SQLite is the default development convenience.
- Avoid unrelated frameworks, authentication, or a frontend build pipeline for this API milestone.
- Keep README examples and OpenAPI consistent with behavior. Add regression tests for fixes.
