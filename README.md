# Bharat

An Indian postal directory API built with Django REST Framework and SQLite. Look up the offices associated with a PIN, search by office or district, browse states and districts, and inspect where the data came from. Read the [project write-up](http://localhost:3000/projects/bharat) for background.

**Status:** API milestone. The repository ships `db.sqlite3` with the verified Bharat directory: 155,599 offices from the project's 2023 snapshot. It has no coordinates. Its source date is on or before June 2023: the file was committed to this repository on 28 June 2023. `fetch_postal_data` replaces it with the Department of Posts' official [All India Pincode Directory](https://www.data.gov.in/resource/all-india-pincode-directory-till-last-month) once you have a data.gov.in API key. No hosted deployment exists yet. A PIN may map to multiple offices. Bharat lists post offices and whether each one delivers mail; it cannot tell you whether a particular street address exists.

## Get the code

Install [Git](https://git-scm.com/downloads), then clone the repository and enter it:

```sh
git clone https://github.com/code-kasha/bharat.git
cd bharat
```

The clone includes `db.sqlite3` (about 28 MB) with the bundled directory. Every command below runs from this `bharat` folder.

## Quick start

Requires Python 3.13 and [uv](https://docs.astral.sh/uv/). The bundled `db.sqlite3` already contains data.

```sh
uv sync --frozen
uv run python manage.py migrate
uv run python manage.py runserver
```

To load current official data instead, get a free data.gov.in API key (sign in at [data.gov.in](https://www.data.gov.in/) and copy it from your account's API key page), then set it in your shell and run `uv run python manage.py fetch_postal_data`:

| Shell | Set the key |
| --- | --- |
| bash, zsh, Git Bash | `export DATA_GOV_IN_API_KEY=your-key` |
| PowerShell | `$env:DATA_GOV_IN_API_KEY = "your-key"` |
| cmd | `set DATA_GOV_IN_API_KEY=your-key` |

The public sample key is capped at 10 records, so it cannot load the directory.

> **Known blocker (checked 26 September 2026):** data.gov.in's sign-up form does not display its captcha, so new accounts cannot be created and no API key can be issued. Until the portal is fixed, the fetch cannot run; use the bundled 2023 snapshot or [upload your own CSV](#changing-the-source). An existing key should still work, but no live fetch has been run yet.

Open the [lookup page](http://127.0.0.1:8000/), the [API documentation](http://127.0.0.1:8000/api/docs/) or [a PIN lookup in JSON](http://127.0.0.1:8000/api/v1/pincodes/110001/).

## Lookup page

`GET /` is a server-rendered search page for people. Enter a 6-digit PIN or at least 2 characters of an office or district name. Every page shows where the data came from and how current it is: source, source date (exact, approximate such as "On or before June 2023", or "not recorded"), load date and office count. When changing the source is enabled, the source line links to [the change-source page](#changing-the-source).

Each search, results page or error costs **one HTTP request**. The CSS is inline; there is no JavaScript, web font, image or external asset, and the page declares an inline icon so browsers skip `/favicon.ico`. That path answers with a cached empty response for browsers that request it anyway. Each lookup uses three database queries: dataset label, result count and one page of 25 offices.

The page is built for keyboard and screen-reader use. It has a skip link, a labelled search box with its hint and any error linked through `aria-describedby` and `aria-invalid`, and "Error:" in the page title when input is rejected (with HTTP 400). Results are in a captioned table with row and column headers. Visible focus outlines, light and dark colour schemes, and a table that scrolls inside its own keyboard-focusable region on narrow screens complete it.

## Changing the source

Bharat is meant to run locally, so you can replace the directory with your own CSV from the browser. Follow **change source** on the home page, or open [`/source/`](http://127.0.0.1:8000/source/). Choose the file, say where it came from, and optionally give either an exact source date or an approximate one such as "2024–2025". Leave both empty if you do not know; Bharat never guesses a date.

The CSV uses the directory's column layout: `Circle Name`, `Region Name`, `Division Name`, `Office Name`, `Pincode`, `OfficeType`, `Delivery`, `District` and `StateName`, in any order. Spaces, underscores and case in column names are ignored. `Latitude` and `Longitude` are optional; other columns are ignored. The file must be UTF-8 (Excel's "CSV UTF-8") and at most 100 MB.

The upload goes through the same importer as `fetch_postal_data`. The whole file is validated before anything is written; any invalid row rejects the file, the page lists up to 10 problems by CSV line number, and the current directory stays untouched. A valid file replaces every office and the source details in one transaction. Exact repeated rows are merged; an office listed twice with different details (same PIN, state, district and office name) is rejected.

The page has no login, so it is enabled only for local use. It is on while `DJANGO_DEBUG` is `true`, which is the default for `runserver` and the Docker image, and off otherwise. `BHARAT_ALLOW_SOURCE_CHANGE=false` turns it off locally; `true` forces it on. When it is off, `/source/` returns 404 and the link is hidden. The form is protected by Django's CSRF check.

The upload changes the database it runs against: `db.sqlite3` in a clone, or `/data/bharat.sqlite3` in a container. To keep the bundled data, run `git restore db.sqlite3` in a clone; a container without a volume starts from the bundled data again.

## API

All data endpoints are read-only and public. Writes happen only through the importer, via the fetch management command or the local [change-source page](#changing-the-source).

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
| `GET /api/v1/export/` | The whole directory as one JSON file in one request; see [Downloading the whole directory](#downloading-the-whole-directory) |
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

## Downloading the whole directory

`GET /api/v1/export/` returns dataset metadata and every office in a single streamed JSON document: `{"dataset": {...}, "offices": [...]}`. Offices have the same fields as the list endpoints. There is no pagination, so one request downloads everything:

```sh
curl -OJ --compressed http://127.0.0.1:8000/api/v1/export/
```

- **Versioned:** the file is named `bharat-offices-<source date or "undated">-<first 12 characters of the SHA256>.json`, and the response ETag is the full dataset SHA256.
- **Compressed:** clients that send `Accept-Encoding: gzip` (browsers, `curl --compressed`) receive 1.4 MB instead of 42.9 MB for the bundled directory.
- **Not resent:** a client that sends its ETag back in `If-None-Match` gets `304 Not Modified` with no body until the dataset changes.
- **Streamed:** the server reads offices in batches of 5,000 and never holds the whole directory in memory.

## Fetching the dataset

With `DATA_GOV_IN_API_KEY` set in your shell (see [Quick start](#quick-start)):

```sh
uv run python manage.py fetch_postal_data --dry-run
uv run python manage.py fetch_postal_data
```

The command reads the key only from `DATA_GOV_IN_API_KEY`, never from a command-line argument, so it does not appear in process listings. It pages through the API (`--page-size`, default 1000) and retries transient gateway errors. It refuses a download that is shorter than the total the API reports. `--resource` selects another OGD resource ID with the same fields.

The importer validates the complete download before writing. It keeps six-digit PINs as strings, collapses identical records, rejects conflicting identities and refuses empty snapshots. Office identity is PIN + state + district + office name (case-insensitive during import). A failed fetch leaves the current directory untouched. A successful fetch replaces the entire directory and metadata in one transaction. Repeating a fetch that returns identical data is a no-op. Database-generated IDs are deliberately not exposed as stable public identifiers. The database itself does not enforce office uniqueness, so a database built from another snapshot may hold repeated identities; the fetch still rejects them.

Provenance is recorded from the source itself. The source is the API resource URL (never the key). The source date is the API's reported `updated_date` and is left empty if the API does not report one. The SHA256 covers the downloaded records.

Upstream updates the directory roughly monthly. Refresh by re-running the command, for example from a scheduled job. If upstream publishes conflicting records, the fetch fails and lists them, and the previous data stays in service.

## Architecture

- `config/`: settings, URL routing, WSGI entrypoint.
- `postal/models.py`: current dataset metadata and indexed office records.
- `postal/importer.py`: API download, validation, duplicate detection and atomic replacement.
- `postal/management/commands/`: operator-only fetch entrypoint.
- `postal/serializers.py` and `views.py`: validation, read-only API and generated schema.
- `postal/queries.py`: PIN and search rules shared by the API and the lookup page.
- `postal/web.py` and `templates/postal/`: the one-request lookup page and the local change-source page.
- `postal/export.py`: the streamed, versioned whole-directory download.
- `tests/`: synthetic API-shaped fixtures (no network), fetch/rollback regressions, API behavior.

The design deliberately keeps one directory snapshot, no user accounts, and no runtime dependency on the upstream API. SQLite runs in WAL mode, so reads continue during a replacement. Writers use immediate transactions, so concurrent fetches are serialized. PIN lookup uses an indexed exact match. Place search uses substring matching; it is not fuzzy search. Django 5.2 is an [LTS release](https://docs.djangoproject.com/en/5.2/releases/5.2/).

## Performance

Measured on 26 September 2026 with the bundled 155,599-office database on a Windows laptop, in-process through Django's test client (no network). Values are medians of 30 requests after one warm-up; "queries" counts database queries per request.

| Request | Median | p95 | Queries |
| --- | ---: | ---: | ---: |
| PIN lookup, API or page (`110001`, 23 offices) | 2.3 ms | 2.9 ms | 3 |
| Home page / dataset metadata | 1 ms | 1.5 ms | 1 |
| Search `market`, API or page (140 matches) | 78 ms | 81 ms | 2–3 |
| Search with no matches (`zzqx`) | 49 ms | 59 ms | 2 |
| Search `an` (64,904 matches) | 95 ms | 113 ms | 2 |
| State filter (`Kerala`) | 39 ms | 44 ms | 2 |
| States list | 18 ms | 20 ms | 2 |
| Districts list (all states) | 202 ms | 215 ms | 2 |
| Districts for one state | 31 ms | 36 ms | 2 |
| Full export, one request | 1.2 s (42.9 MB; 1.4 MB gzip) | | 3 |

PIN lookups use the PIN index. Search scans the table because substring matching (`LIKE '%term%'`) cannot use an index; at this size that stays under about 0.1 s. The all-states districts list groups the whole table on each request. A composite `(state, district)` index was measured on a copy of the database to cut that query from about 92 ms to 0.5 ms (page count from 109 ms to 15 ms), but it adds 4.4 MB to `db.sqlite3`, so it is not included.

## Configuration

Environment variables are read by Django. `.env` files are not automatically loaded by Django; use `uv run --env-file .env ...` if you create one from `.env.example`.

| Variable | Local default / purpose |
| --- | --- |
| `DJANGO_DEBUG` | `true`; must be `false` on a public deployment |
| `DJANGO_SECRET_KEY` | Development-only fallback; provide a generated secret in production |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1]`; comma-separated hostnames |
| `SQLITE_PATH` | `db.sqlite3` in the repository; `/data/bharat.sqlite3` in the container |
| `BHARAT_ALLOW_SOURCE_CHANGE` | Follows `DJANGO_DEBUG`; enables the local [change-source page](#changing-the-source) |
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

## Run with Docker

These commands are identical in bash, zsh, PowerShell, cmd and Git Bash. From the repository root, once Docker's engine is running:

```sh
docker build -t bharat:local .
docker run -d --rm --name bharat-demo -p 127.0.0.1:18000:8000 bharat:local
```

The image bundles `db.sqlite3` as `/data/bharat.sqlite3` and applies migrations when it starts, so the API serves the full directory immediately. Open these in a browser, or fetch them with `curl` (in Windows PowerShell 5.1 type `curl.exe`, because `curl` is an alias there):

- [health](http://127.0.0.1:18000/health/) should report `ok`
- [dataset](http://127.0.0.1:18000/api/v1/dataset/) should report `row_count: 155599`
- [PIN 110001](http://127.0.0.1:18000/api/v1/pincodes/110001/) should return 23 offices
- [API documentation](http://127.0.0.1:18000/api/docs/)

When finished, run `docker stop bharat-demo`; `--rm` removes the container.

Each new container starts from the bundled database. To keep data you fetch inside the container, add a named volume; on first use, Docker seeds an empty named volume with the bundled database. Set `DATA_GOV_IN_API_KEY` in your shell as shown in [Quick start](#quick-start). `-e DATA_GOV_IN_API_KEY` with no value passes it through without the key appearing in the command:

```sh
docker run -d --rm --name bharat-demo -v bharat-data:/data -p 127.0.0.1:18000:8000 bharat:local
docker exec -e DATA_GOV_IN_API_KEY bharat-demo python manage.py fetch_postal_data
```

An existing volume keeps its own data and is not updated when you rebuild the image. Remove it with `docker volume rm bharat-data` to go back to the bundled database.

The image puts its virtualenv on `PATH`, so container commands are written as `python manage.py ...`. Avoid passing arguments that start with `/` (such as `/app/.venv/bin/python`): Git Bash on Windows rewrites them into Windows paths.

Verified on 26 September 2026 with Docker Desktop (Engine 29.8.0, Compose 5.5.1) on WSL 2.7.14. The image build, startup migrations, health, dataset, PIN lookup, district filter, search, documentation, write rejection (405), non-root user, named-volume seeding and `docker exec` from PowerShell and Git Bash all passed. These are tested versions, not minimum requirements.

### Installing Docker on Windows

On macOS or Linux, install Docker Desktop or Docker Engine from the [official documentation](https://docs.docker.com/get-started/get-docker/). On Windows, install Docker Desktop with the WSL 2 backend. See the [official Windows installation guide](https://docs.docker.com/desktop/setup/install/windows-install/) for current system requirements.

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


## CI and release delivery

GitHub Actions installs the frozen lockfile, checks formatting/lint, runs tests, validates migrations/OpenAPI and builds the container. A `v*` Git tag publishes a versioned image to `ghcr.io/<owner>/<repository>` only after these checks pass. CI does not contact data.gov.in. No image has been published yet.

The Docker image uses Gunicorn and an unprivileged user, and stores the SQLite database in `/data`. Build with `docker build -t bharat:local .`.

Hosting is out of scope for now; the project is meant to run locally, with or without Docker. When hosting is needed, use one container with a persistent volume at `/data`: SQLite must not be shared across hosts or network filesystems. Also set `DJANGO_DEBUG=false`, a generated `DJANGO_SECRET_KEY` and `DJANGO_ALLOWED_HOSTS`, put TLS ingress in front, and back up `/data/bharat.sqlite3` before migrations.

## Next milestones

- Run the first live fetch from data.gov.in once an API key is available (blocked by the broken sign-up captcha; see [Quick start](#quick-start)).
- Choose a hosting platform when a public deployment is needed.

## License

The code is released under the [MIT License](LICENSE). Data fetched from data.gov.in is published under the Government Open Data License – India; keep its attribution requirements.
