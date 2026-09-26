An Indian postal directory API built with Django REST Framework and SQLite. Look up the offices associated with a PIN, search by office or district, browse states and districts, and inspect where the data came from. Read the [project write-up](http://localhost:3000/projects/bharat-post-dir) for background.

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/images/home-dark.png">
  <img src="docs/images/home-light.png" width="1280" alt="The bharat-post-dir lookup page: a search box for a PIN or place name, and an 'About this data' panel giving the source (verified by the project maintainer), the source date (on or before June 2023), the load date and 155,599 offices, 3 of them listed more than once.">
</picture>

**Status:** API milestone. The repository ships `db.sqlite3` with the verified directory: 155,599 offices from the project's 2023 snapshot. It has no coordinates. Its source date is on or before June 2023: the file was committed to this repository on 28 June 2023. `fetch_postal_data` replaces it with the Department of Posts' official [All India Pincode Directory](https://www.data.gov.in/resource/all-india-pincode-directory-till-last-month) once you have a data.gov.in API key. bharat-post-dir runs in production mode by default, locally and in Docker; to use your own dataset, run it locally or [deploy it yourself](#deploying-it-yourself). No hosted deployment exists yet. A PIN may map to multiple offices. bharat-post-dir lists post offices and whether each one delivers mail; it cannot tell you whether a particular street address exists.

## Get the code

Install [Git](https://git-scm.com/downloads), then clone the repository and enter it:

```sh
git clone https://github.com/code-kasha/bharat-post-dir.git
cd bharat-post-dir
```

The clone includes `db.sqlite3` (about 28 MB) with the bundled directory. Every command below runs from this `bharat-post-dir` folder.

## Quick start

Requires Python 3.13 and [uv](https://docs.astral.sh/uv/). The bundled `db.sqlite3` already contains data.

```sh
uv sync --frozen
uv run python manage.py migrate
uv run python manage.py runserver
```

This runs in **production mode** (`DJANGO_DEBUG=false`), the default everywhere: no debug pages, and a random secret key created once in `.secret_key` next to the database (gitignored). Uploads on the [change-source page](#changing-the-source) are temporary and seen only by your browser. **Contributor mode** is opt-in: set `DJANGO_DEBUG=true` to get Django's debug pages and to save uploads over `db.sqlite3` so you can share them.

| Shell | Contributor mode |
| --- | --- |
| bash, zsh, Git Bash | `DJANGO_DEBUG=true uv run python manage.py runserver` |
| PowerShell | `$env:DJANGO_DEBUG = "true"`, then `uv run python manage.py runserver` |
| cmd | `set DJANGO_DEBUG=true`, then `uv run python manage.py runserver` |

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

bharat-post-dir is meant to run locally, so you can try or replace the directory with your own CSV or JSON file from the browser. Follow **change source** on the home page, or open [`/source/`](http://127.0.0.1:8000/source/). Choose the file, say where it came from, and optionally give either an exact source date or an approximate one such as "2024–2025". Leave both empty if you do not know; bharat-post-dir never guesses a date.

The format is detected from the file's content, not its name:

- **CSV** uses the directory's column layout: `Circle Name`, `Region Name`, `Division Name`, `Office Name`, `Pincode`, `OfficeType`, `Delivery`, `District` and `StateName`, in any order. Spaces, underscores and case in column names are ignored. `Latitude` and `Longitude` are optional; other columns are ignored.
- **JSON** can be bharat-post-dir's own [whole-directory download](#downloading-the-whole-directory) (`{"dataset": ..., "offices": [...]}`), a data.gov.in API response (`{"records": [...]}`), or a plain list of offices. Offices use the CSV column names or bharat-post-dir's field names (`office_name`, `pincode`, `state`, `circle`, `region`, `division`, `office_type`, `delivery`, `district`, `latitude`, `longitude`). A bharat-post-dir download records its own source and date, which fill in the form fields you leave empty; anything you type wins.

Either way the file must be UTF-8 (Excel's "CSV UTF-8") and at most 100 MB. Problems are listed by CSV line number or JSON record number.

The upload goes through the same importer as `fetch_postal_data`. The whole file is validated before anything is written; any invalid row rejects the file, the page lists up to 10 problems by CSV line number, and nothing is kept. Exact repeated rows are merged. An office listed more than once with different details (same PIN, state, district and office name) is kept in every version, because government data can list an office twice legitimately; the page, `/api/v1/dataset/` (`repeated_identity_count`) and the upload result say how many there are.

What happens to a valid file depends on the mode:

- **Default (production) mode: temporary.** The upload is stored in its own scratch SQLite file under `.uploads/` next to the database, named by a signed, HTTP-only cookie. Only that browser sees it, on the lookup page and in search; the API, the export and `db.sqlite3` keep the default dataset. The data panel shows the upload's details and when it will be deleted (after 24 hours), with a **Back to the default dataset** button. To save and share an upload, run with `DJANGO_DEBUG=true` and upload it again. A new upload replaces the browser's previous one, and at most 5 uploads are kept at once; the oldest is deleted first.
- **Contributor mode (`DJANGO_DEBUG=true`): saved.** A valid file replaces every office and the source details in `db.sqlite3` (or whatever `SQLITE_PATH` names) in one transaction, and the write-ahead log is folded into the file so it can be committed as-is. The page then shows a **Share this dataset** note: the git commands to commit `db.sqlite3` on a branch, and a ready-made description (source, source date or period, office count, SHA256) for a pull request on this repository or for your own published fork. Pull requests may not be reviewed, so publishing your fork is just as good. To go back to the bundled data, run `git restore db.sqlite3`.

The page has no login, so it is for local use. It is on by default when you run bharat-post-dir from a clone. A hosted site must set `SITE_ALLOW_SOURCE_CHANGE=false`; the Docker image, which is meant for hosting, already does. When it is off, `/source/` returns 404 and the link is hidden. To use your own dataset with the hosted setup, run bharat-post-dir locally or deploy it yourself. The forms are protected by Django's CSRF check.

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

- **Versioned:** the file is named `post-offices-<source date or "undated">-<first 12 characters of the SHA256>.json`, and the response ETag is the full dataset SHA256.
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

The importer validates the complete download before writing. It keeps six-digit PINs as strings, collapses identical records, keeps and counts offices listed more than once with different details, and refuses empty snapshots. Office identity is PIN + state + district + office name (case-insensitive during import). A failed fetch leaves the current directory untouched. A successful fetch replaces the entire directory and metadata in one transaction. Repeating a fetch that returns identical data is a no-op. Database-generated IDs are deliberately not exposed as stable public identifiers. Neither the database nor the importer enforces office uniqueness: the bundled snapshot lists 3 offices twice with different details, and a fetch or upload keeps such rows too.

Provenance is recorded from the source itself. The source is the API resource URL (never the key). The source date is the API's reported `updated_date` and is left empty if the API does not report one. The SHA256 covers the downloaded records.

Upstream updates the directory roughly monthly. Refresh by re-running the command, for example from a scheduled job. If upstream lists an office more than once with different details, every version is kept and the command reports how many.

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

The design deliberately keeps one directory snapshot, no user accounts, and no runtime dependency on the upstream API. SQLite runs in WAL mode, so reads continue during a replacement. Writers use immediate transactions, so concurrent fetches are serialized. PIN lookup uses an indexed exact match. Place search uses substring matching; it is not fuzzy search. Django 5.2 is an [LTS release](https://docs.djangoproject.com/en/5.2/releases/5.2/) with security support until April 2028.

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
| `DJANGO_DEBUG` | `false` (production mode); `true` is contributor mode and saves uploads over the database |
| `DJANGO_SECRET_KEY` | Optional; without it a random key is created once in `.secret_key` next to the database (`/data/.secret_key` in the container) and reused |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1]`; comma-separated hostnames |
| `SQLITE_PATH` | `db.sqlite3` in the repository; `/data/db.sqlite3` in the container |
| `SITE_ALLOW_SOURCE_CHANGE` | `true` in a clone, `false` in the Docker image; enables the local [change-source page](#changing-the-source). Set `false` on any hosted site |
| `DATA_GOV_IN_API_KEY` | Required only by `fetch_postal_data` |
| `DJANGO_HTTPS` | `false`; `true` turns on the HTTPS redirect, HSTS (one year) and secure cookies. Only for a site served over HTTPS |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Empty; comma-separated origins such as `https://example.com` for a hosted site |
| `TRUST_PROXY_HTTPS` | `false`; enable only behind a trusted TLS proxy that overwrites `X-Forwarded-Proto` (see [Deploying it yourself](#deploying-it-yourself)) |

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

Tests cover one-to-many PIN lookup, input validation, filters, pagination, state/district listings, read-only routes, provenance, API pagination, truncated or malformed downloads, retries, duplicate merging, repeated offices kept and counted, idempotence, dry runs and rollback. They also cover the lookup page (one request, three queries, accessibility markup), the export, production-mode settings, CSV and JSON uploads in every shape, temporary per-browser uploads (isolation, expiry, the size and count caps, CSRF, going back to the default dataset), saved uploads and the share note. They never contact data.gov.in. GitHub Actions runs all of these checks and a Docker build on every push; on 26 September 2026, 113 tests passed there and locally.

## Run with Docker

These commands are identical in bash, zsh, PowerShell, cmd and Git Bash. From the repository root, once Docker's engine is running:

```sh
docker build -t bharat-post-dir:local .
docker run -d --rm --name app-demo -p 127.0.0.1:18000:8000 bharat-post-dir:local
```

The image bundles `db.sqlite3` as `/data/db.sqlite3` and applies migrations when it starts, so the API serves the full directory immediately. It is built for hosting: it runs in production mode, and the change-source page is off (`SITE_ALLOW_SOURCE_CHANGE=false`). To try uploads in a local container, add `-e SITE_ALLOW_SOURCE_CHANGE=true` to `docker run`; never do that on a public server. Open these in a browser, or fetch them with `curl` (in Windows PowerShell 5.1 type `curl.exe`, because `curl` is an alias there):

- [health](http://127.0.0.1:18000/health/) should report `ok`
- [dataset](http://127.0.0.1:18000/api/v1/dataset/) should report `row_count: 155599`
- [PIN 110001](http://127.0.0.1:18000/api/v1/pincodes/110001/) should return 23 offices
- [API documentation](http://127.0.0.1:18000/api/docs/)

When finished, run `docker stop app-demo`; `--rm` removes the container.

Each new container starts from the bundled database. To keep data you fetch inside the container, add a named volume; on first use, Docker seeds an empty named volume with the bundled database. Set `DATA_GOV_IN_API_KEY` in your shell as shown in [Quick start](#quick-start). `-e DATA_GOV_IN_API_KEY` with no value passes it through without the key appearing in the command:

```sh
docker run -d --rm --name app-demo -v app-data:/data -p 127.0.0.1:18000:8000 bharat-post-dir:local
docker exec -e DATA_GOV_IN_API_KEY app-demo python manage.py fetch_postal_data
```

An existing volume keeps its own data and is not updated when you rebuild the image. Remove it with `docker volume rm app-data` to go back to the bundled database.

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

## Deploying it yourself

Run one container on a server with a persistent volume at `/data`, and put a TLS reverse proxy in front of it. SQLite must stay on that one volume: never share it across hosts or put it on a network filesystem. The image runs Gunicorn with two workers as an unprivileged user.

The commands below are for a Linux server shell. Replace `example.com` with your domain, and point its DNS at the server first so the proxy can obtain a certificate.

1. Build the image on the server (or push it from elsewhere), and create a network the proxy and the app share:

   ```sh
   docker build -t bharat-post-dir:local .
   docker network create app-net
   ```

2. Start bharat-post-dir. It publishes no port, so it is reachable only through the proxy:

   ```sh
   docker run -d --name app --restart unless-stopped --network app-net \
     -v app-data:/data \
     -e DJANGO_ALLOWED_HOSTS=example.com \
     -e DJANGO_CSRF_TRUSTED_ORIGINS=https://example.com \
     -e DJANGO_HTTPS=true -e TRUST_PROXY_HTTPS=true \
     -e SITE_ALLOW_SOURCE_CHANGE=false \
     bharat-post-dir:local
   ```

   On first use the empty `app-data` volume is seeded with the bundled directory. The secret key is created once in `/data/.secret_key` on the volume, so it survives restarts; set `DJANGO_SECRET_KEY` instead if you prefer to manage it. `SITE_ALLOW_SOURCE_CHANGE=false` is the image's default, repeated so a hosted site never enables the unauthenticated change-source page. To serve your own dataset, load it locally in contributor mode first and build the image from that `db.sqlite3`, or run `fetch_postal_data` in the container.

3. Put [Caddy](https://caddyserver.com/) in front for HTTPS. Save this as `Caddyfile`:

   ```text
   example.com {
       reverse_proxy app:8000
   }
   ```

   ```sh
   docker run -d --name caddy --restart unless-stopped --network app-net \
     -p 80:80 -p 443:443 \
     -v ./Caddyfile:/etc/caddy/Caddyfile:ro -v caddy-data:/data \
     caddy:2
   ```

   Caddy obtains and renews the certificate, and sets `X-Forwarded-Proto` itself, replacing any value a client sends. That is what makes `TRUST_PROXY_HTTPS=true` safe. Without it, `DJANGO_HTTPS=true` would redirect forever, because bharat-post-dir would see plain HTTP from the proxy. Only use `TRUST_PROXY_HTTPS` behind a proxy that overwrites the header like this.

4. Check `https://example.com/health/` (it reports `ok`), the lookup page and `/api/v1/dataset/`. `/source/` should return 404. HSTS tells browsers to insist on HTTPS for a year, so enable `DJANGO_HTTPS` only once HTTPS works.

**Backups.** The directory and the secret key live on the volume. Copy a consistent snapshot of the database with SQLite's backup API, then copy it off the server:

```sh
docker exec app python -c "import sqlite3; sqlite3.connect('/data/db.sqlite3').backup(sqlite3.connect('/data/backup.sqlite3'))"
docker cp app:/data/backup.sqlite3 ./db-backup.sqlite3
```

Back up before every update, because migrations run automatically when the container starts.

**Updates.** Build or pull the new image, then replace the container with the same volume and settings: `docker stop app && docker rm app`, then the `docker run` from step 2. The volume keeps its data; a rebuilt image does not replace an existing volume's directory. To switch to the directory bundled in a new image, remove the volume (`docker volume rm app-data`) before starting the container.

**Rollback.** Migrations only move forward, so roll back the image and the data together. Stop and remove the container, then restore the backup into the volume from the folder that holds `db-backup.sqlite3`:

```sh
docker run --rm -v app-data:/data -v "$PWD":/backup --entrypoint sh bharat-post-dir:local \
  -c "rm -f /data/db.sqlite3 /data/db.sqlite3-wal /data/db.sqlite3-shm && cp /backup/db-backup.sqlite3 /data/db.sqlite3"
```

This runs as the image's unprivileged user, so the restored file stays writable by bharat-post-dir; a restore done as root (for example with a plain `alpine` container) leaves a database the app can read but not update. Then start the previous image tag with the step 2 command.

**Verified** on 26 September 2026 with Docker Engine 29.3.1 and Caddy 2 in a Linux sandbox, using `localhost` and Caddy's local certificate in place of a domain: HTTP-to-HTTPS redirect, HSTS and security headers, health, the lookup page and search, the PIN API, API docs, the gzipped export with `304` on its ETag, `/source/` off, unknown hosts refused, and data and the secret key surviving a restart and a container replacement, plus the backup and rollback commands above. Not verified there: a real domain's public certificate, its renewal, and the server's firewall. (The sandbox needed a registry mirror and its proxy certificate to build; neither is part of the image.)

**Support window.** bharat-post-dir uses Django 5.2 LTS, whose security support ends in April 2028. A fork should upgrade Django before running bharat-post-dir publicly after that.

## Next milestones

- Run the first live fetch from data.gov.in once an API key is available (blocked by the broken sign-up captcha; see [Quick start](#quick-start)).
- Choose a hosting platform when a public deployment is needed.

## Contributing and license

bharat-post-dir is complete as of v1.0.0 and not actively maintained: it works as-is, and issues or pull requests may go unanswered. Fork it freely. The code is under the [MIT License](LICENSE) with no extra conditions. Data fetched from data.gov.in is published under the Government Open Data License – India; keep its attribution requirements.

If you update the dataset, please share it back, either with a pull request or by publishing your fork. [`CONTRIBUTING.md`](CONTRIBUTING.md) explains how, and how to run the checks. A mention is appreciated, never required.
