# Bharat

An Indian postal directory API built with Django REST Framework and SQLite. Look up the offices associated with a PIN, search by office or district, browse states and districts, and inspect where the data came from.

**Status:** API milestone. The repository ships `db.sqlite3` with the verified Bharat directory: 155,599 offices from the project's 2023 snapshot. It has no coordinates, and its source date is not recorded. `fetch_postal_data` replaces it with the Department of Posts' official [All India Pincode Directory](https://www.data.gov.in/resource/all-india-pincode-directory-till-last-month) once you have a data.gov.in API key. No hosted deployment exists yet. A PIN may map to multiple offices; this service does not verify that a street address is deliverable.

## Quick start

Requires Python 3.13 and [uv](https://docs.astral.sh/uv/). The bundled `db.sqlite3` already contains data.

```sh
uv sync --frozen
uv run python manage.py migrate
uv run python manage.py runserver
```

To load current official data instead, get a free data.gov.in API key (sign in at [data.gov.in](https://www.data.gov.in/) and copy it from your account's API key page) and run `DATA_GOV_IN_API_KEY=your-key uv run python manage.py fetch_postal_data`. In PowerShell, set the key first with `$env:DATA_GOV_IN_API_KEY = "your-key"`. The public sample key is capped at 10 records, so it cannot load the directory.

Open [API documentation](http://127.0.0.1:8000/api/docs/) or [a PIN lookup](http://127.0.0.1:8000/api/v1/pincodes/110001/).

## API

All data endpoints are read-only and public. Writes happen only through the fetch management command.

| Endpoint | Behavior |
| --- | --- |
| `GET /api/v1/pincodes/110001/` | Matching offices, paginated; malformed PIN is 400, absent PIN is 404 |
| `GET /api/v1/offices/?search=market` | Search office names and districts |
| `GET /api/v1/offices/?state=Delhi&district=New%20Delhi` | Case-insensitive exact filters; combine with search or pincode |
| `GET /api/v1/states/` | States with their office counts |
| `GET /api/v1/districts/?state=Delhi` | Districts with office counts; `state` is optional and case-insensitive |
| `GET /api/v1/dataset/` | Source, source date, SHA256, import timestamp and counts; 404 before the first fetch |
| `GET /api/schema/` | Generated OpenAPI schema |
| `GET /api/docs/` | Interactive Swagger documentation (UI assets loaded from a CDN) |
| `GET /health/` | Process/database connectivity; does not assert dataset freshness |

Lists return `count`, `next`, `previous`, and `results`, with 25 items per page. Follow `next` to retrieve further matches. Search requires 2–100 characters. An empty list is valid when filters match nothing or before the first fetch.

```json
{
  "count": 1,
  "next": null,
  "previous": null,
  "results": [
    {
      "pincode": "400001",
      "office_name": "Example Office",
      "district": "Example District",
      "state": "Example State",
      "circle": "Example Circle",
      "region": "Example Region",
      "division": "Example Division",
      "office_type": "HO",
      "delivery": "Delivery",
      "latitude": 18.93,
      "longitude": 72.83
    }
  ]
}
```

The office above shows the response shape; its values are illustrative. `latitude` and `longitude` are passed through as published. They are `null` when the source value is missing or not a valid coordinate. The upstream data is known to contain some points outside India, so treat coordinates as approximate.

## Fetching the dataset

```sh
DATA_GOV_IN_API_KEY=your-key uv run python manage.py fetch_postal_data --dry-run
DATA_GOV_IN_API_KEY=your-key uv run python manage.py fetch_postal_data
```

The command reads the key from `DATA_GOV_IN_API_KEY` so it stays out of shell history. It pages through the API (`--page-size`, default 1000) and retries transient gateway errors. It refuses a download that is shorter than the total the API reports. `--resource` selects another OGD resource ID with the same fields.

The importer validates the complete download before writing. It keeps six-digit PINs as strings, collapses identical records, rejects conflicting identities and refuses empty snapshots. Office identity is PIN + state + district + office name (case-insensitive during import). A failed fetch leaves the current directory untouched. A successful fetch replaces the entire directory and metadata in one transaction. Repeating a fetch that returns identical data is a no-op. Database-generated IDs are deliberately not exposed as stable public identifiers. The database itself does not enforce office uniqueness, so a database built from another snapshot may hold repeated identities; the fetch still rejects them.

Provenance is recorded from the source itself. The source is the API resource URL (never the key). The source date is the API's reported `updated_date` and is left empty if the API does not report one. The SHA256 covers the downloaded records.

Upstream updates the directory roughly monthly. Refresh by re-running the command, for example from a scheduled job. If upstream publishes conflicting records, the fetch fails and lists them, and the previous data stays in service.

## Architecture

- `config/`: settings, URL routing, WSGI entrypoint.
- `postal/models.py`: current dataset metadata and indexed office records.
- `postal/importer.py`: API download, validation, duplicate detection and atomic replacement.
- `postal/management/commands/`: operator-only fetch entrypoint.
- `postal/serializers.py` and `views.py`: validation, read-only API and generated schema.
- `tests/`: synthetic API-shaped fixtures (no network), fetch/rollback regressions, API behavior.

The design deliberately keeps one directory snapshot, no user accounts, and no runtime dependency on the upstream API. SQLite runs in WAL mode, so reads continue during a replacement. Writers use immediate transactions, so concurrent fetches are serialized. PIN lookup uses an indexed exact match. Place search uses substring matching; it is not fuzzy search and has not been benchmarked at production traffic levels. Django 5.2 is an [LTS release](https://docs.djangoproject.com/en/5.2/releases/5.2/).

## Configuration

Environment variables are read by Django. `.env` files are not automatically loaded by Django; use `uv run --env-file .env ...` if you create one from `.env.example`.

| Variable | Local default / purpose |
| --- | --- |
| `DJANGO_DEBUG` | `true`; must be `false` on a public deployment |
| `DJANGO_SECRET_KEY` | Development-only fallback; provide a generated secret in production |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1]`; comma-separated hostnames |
| `SQLITE_PATH` | `db.sqlite3` in the repository; `/data/bharat.sqlite3` in the container |
| `DATA_GOV_IN_API_KEY` | Required only by `fetch_postal_data` |
| `TRUST_PROXY_HTTPS` | `false`; enable only behind a trusted TLS proxy that strips incoming forwarding headers |

Only the bundled `db.sqlite3` is tracked; other databases and SQLite's `-wal`/`-shm` files are gitignored. Committing a refreshed `db.sqlite3` adds its full size to Git history each time.

## Validation

```sh
uv run ruff check .
uv run ruff format --check .
uv run pytest
uv run python manage.py check
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py spectacular --validate --fail-on-warn --file schema.yml
```

Tests cover one-to-many PIN lookup, input validation, filters, pagination, state/district listings, read-only routes, provenance, API pagination, truncated or malformed downloads, retries, duplicate/conflict handling, idempotence, dry runs and rollback. They never contact data.gov.in.

## Docker setup on Windows

Install Docker Desktop with the WSL 2 backend. See the [official Windows installation guide](https://docs.docker.com/desktop/setup/install/windows-install/) for current system requirements.

1. Open PowerShell **as Administrator** and install WSL without an additional Linux distribution:

   ```powershell
   wsl --install --no-distribution
   ```

   Restart Windows if prompted. Docker manages its own Linux environment; Ubuntu is not required for these commands.

2. Install Docker Desktop using WinGet, or use the installer linked in the official guide:

   ```powershell
   winget install --id Docker.DockerDesktop --exact --source winget
   ```

   Select the WSL 2 backend if prompted. Open Docker Desktop, complete its initial setup, and wait for the engine to start.

3. Open a new PowerShell window and verify both the client and engine:

   ```powershell
   wsl --version
   docker --version
   docker version
   docker compose version
   ```

   `docker version` should display both **Client** and **Server** sections. A client version alone does not confirm the engine is running.

If `docker` is not recognized, reopen the terminal after installation. For a per-user installation, check the executable directly:

```powershell
& "$env:LOCALAPPDATA\Programs\DockerDesktop\resources\bin\docker.exe" version
```

If the error mentions a missing `dockerDesktopLinuxEngine` pipe, open Docker Desktop and wait for startup. If WSL is missing, complete step 1; if it needs an update, run `wsl --update` in Administrator PowerShell and restart Docker Desktop.

### Run Bharat in a local container

From the repository root, after Docker's engine is ready:

```powershell
docker build -t bharat:local .
docker run -d --rm --name bharat-demo -p 127.0.0.1:18000:8000 bharat:local
```

The image bundles `db.sqlite3` as `/data/bharat.sqlite3` and applies migrations when it starts, so the API serves the full directory immediately. Check it:

```powershell
Invoke-RestMethod http://127.0.0.1:18000/health/
Invoke-RestMethod http://127.0.0.1:18000/api/v1/dataset/
Invoke-RestMethod http://127.0.0.1:18000/api/v1/pincodes/110001/
```

The health response should report `ok`, the dataset response should report `row_count: 155599`, and PIN 110001 should return 23 offices. Open [container API documentation](http://127.0.0.1:18000/api/docs/) to explore the endpoints. When finished, run `docker stop bharat-demo`; `--rm` removes the container.

Each new container starts from the bundled database. To keep data you fetch inside the container, add a named volume. On first use, Docker seeds an empty named volume with the bundled database:

```powershell
docker run -d --rm --name bharat-demo -v bharat-data:/data -p 127.0.0.1:18000:8000 bharat:local
docker exec -e DATA_GOV_IN_API_KEY=$env:DATA_GOV_IN_API_KEY bharat-demo /app/.venv/bin/python manage.py fetch_postal_data
```

An existing volume keeps its own data and is not updated when you rebuild the image. Remove it with `docker volume rm bharat-data` to go back to the bundled database. Run `docker exec` from PowerShell or cmd; Git Bash rewrites `/app/...` paths unless you set `MSYS_NO_PATHCONV=1`.

Verified on 26 September 2026 with Docker Desktop (Engine 29.8.0, Compose 5.5.1) on WSL 2.7.14. The image build, startup migrations, health, dataset, PIN lookup, district filter, search, documentation, write rejection (405), non-root user and named-volume seeding all passed. These are tested versions, not minimum requirements.

## CI and release delivery

GitHub Actions installs the frozen lockfile, checks formatting/lint, runs tests, validates migrations/OpenAPI and builds the container. A `v*` Git tag publishes a versioned image to `ghcr.io/<owner>/<repository>` only after these checks pass. CI does not contact data.gov.in. No image has been published yet.

The Docker image uses Gunicorn and an unprivileged user, and stores the SQLite database in `/data`. Build with `docker build -t bharat:local .`.

Hosting is out of scope for now; the project is meant to run locally, with or without Docker. When hosting is needed, use one container with a persistent volume at `/data`: SQLite must not be shared across hosts or network filesystems. Also set `DJANGO_DEBUG=false`, a generated `DJANGO_SECRET_KEY` and `DJANGO_ALLOWED_HOSTS`, put TLS ingress in front, and back up `/data/bharat.sqlite3` before migrations.

## Next milestones

- Run the first live fetch from data.gov.in once an API key is available.
- Add a small accessible lookup interface with source/freshness labels.
- Add versioned data exports and measure query/fetch performance on the full directory.
- Choose a hosting platform when a public deployment is needed.

## License

The code is released under the [MIT License](LICENSE). Data fetched from data.gov.in is published under the Government Open Data License – India; keep its attribution requirements.
