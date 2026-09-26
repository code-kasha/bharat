# Deployment

The Docker image is built for hosting: it runs in production mode with the change-source page off, and bundles the directory so it serves data immediately with no external services. Use it locally to try the image, or on a server behind a TLS proxy.

## Run the image locally

Each release publishes the image as `ghcr.io/code-kasha/bharat-post-dir`, tagged with its version (for example `v1.0.0`) and `latest`, for amd64 and arm64. These commands are identical in bash, zsh, PowerShell, cmd and Git Bash, once Docker's engine is running:

```sh
docker run -d --rm --name app-demo -p 127.0.0.1:18000:8000 ghcr.io/code-kasha/bharat-post-dir:v1.0.0
```

To build the image from a clone instead, run this from the repository root and use `bharat-post-dir:local` in place of the published name, here and in the steps below:

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

Each new container starts from the bundled database. To keep data you fetch inside the container, add a named volume; on first use, Docker seeds an empty named volume with the bundled database. Set `DATA_GOV_IN_API_KEY` in your shell as shown in [Fetching the official directory](datasets.md#fetching-the-official-directory). `-e DATA_GOV_IN_API_KEY` with no value passes it through without the key appearing in the command:

```sh
docker run -d --rm --name app-demo -v app-data:/data -p 127.0.0.1:18000:8000 bharat-post-dir:local
docker exec -e DATA_GOV_IN_API_KEY app-demo python manage.py fetch_postal_data
```

An existing volume keeps its own data and is not updated when you rebuild the image. Remove it with `docker volume rm app-data` to go back to the bundled database.

The image puts its virtualenv on `PATH`, so container commands are written as `python manage.py ...`. Avoid passing arguments that start with `/` (such as `/app/.venv/bin/python`): Git Bash on Windows rewrites them into Windows paths.

Verified on 26 September 2026 with Docker Desktop (Engine 29.8.0, Compose 5.5.1) on WSL 2.7.14. The image build, startup migrations, health, dataset, PIN lookup, district filter, search, documentation, write rejection (405), non-root user, named-volume seeding and `docker exec` from PowerShell and Git Bash all passed. These are tested versions, not minimum requirements.

Installing Docker on Windows is covered in [docker-windows.md](docker-windows.md).

## Deploying it yourself

Run one container on a server with a persistent volume at `/data`, and put a TLS reverse proxy in front of it. SQLite must stay on that one volume: never share it across hosts or put it on a network filesystem. The image runs Gunicorn with two workers as an unprivileged user.

The commands below are for a Linux server shell. Replace `example.com` with your domain, and point its DNS at the server first so the proxy can obtain a certificate.

1. Build the image on the server, or use the published `ghcr.io/code-kasha/bharat-post-dir:v1.0.0` in place of `bharat-post-dir:local` below. Then create a network the proxy and the app share:

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

Also **verified on Windows 11** with Docker Desktop (Engine 29.8.0) and Caddy 2 on 26 September 2026, following steps 1–4 with `localhost` and no workarounds (commands on one line in PowerShell): HTTP-to-HTTPS redirect (308), HSTS, health, the lookup page and a `110001` search (23 results), the dataset (155,599 offices, 3 listed more than once), API docs, the export (`post-offices-undated-959693b760df.json`, 42.9 MB) and its `304`, `/source/` off (404), unknown hosts refused (Caddy does not forward them; the app answers 400), data and the secret key surviving `docker restart app`, a backup that passes SQLite's integrity check, and the rollback restore leaving the database owned and writable by `appuser`.

**Support window.** bharat-post-dir uses Django 5.2 LTS, whose security support ends in April 2028. A fork should upgrade Django before running bharat-post-dir publicly after that.

## Hosted demo

The public demo runs on [Render](https://render.com/)'s free tier until 26 December 2026, then shuts down as planned. Free services sleep after 15 minutes without traffic, so the first request after that takes about a minute. The demo serves the bundled directory read-only, with the change-source page off, so it needs no persistent disk; the secret key lives on the container's temporary disk.

It is built from this repository's `Dockerfile` on `main`. Render's own auto-deploy is off: after every push to `main`, the `deploy` job in CI waits for the checks, triggers Render's deploy hook, and waits until `/health/` reports the new commit (`revision`, which Render provides as `RENDER_GIT_COMMIT`). The job appears as the `production` environment in the repository's Deployments.

To set up the same thing (for a fork, for example):

1. Create a free Render account, then a **Web Service** from the GitHub repository, branch `main`. Render detects the `Dockerfile`; choose the **Free** instance type. The container listens on the `PORT` that Render sets.
2. Set the environment variables, using the service's `onrender.com` host name:
   - `DJANGO_ALLOWED_HOSTS=your-service.onrender.com`
   - `DJANGO_CSRF_TRUSTED_ORIGINS=https://your-service.onrender.com`
   - `SITE_DEMO_UNTIL=2026-12-26`, which shows the end date on every page (leave it out for a permanent site)
3. Set the health check path to `/health/`, and turn **Auto-Deploy** off so only CI deploys, after the checks.
4. Copy the service's **Deploy Hook** URL. In the GitHub repository's **Settings → Secrets and variables → Actions**, add it as the secret `DEPLOY_HOOK_URL`, and add the variable `DEMO_URL` with the service's `https://…onrender.com` address. The `deploy` job is skipped until `DEMO_URL` is set.

Render terminates HTTPS in front of the app. `DJANGO_HTTPS` and `TRUST_PROXY_HTTPS` stay off there: this project has not verified that Render's proxy overwrites `X-Forwarded-Proto`, and the demo has no forms or sessions that need secure cookies.

## Configuration

Environment variables are read by Django. `.env` files are not automatically loaded by Django; use `uv run --env-file .env ...` if you create one from `.env.example`.

| Variable | Local default / purpose |
| --- | --- |
| `DJANGO_DEBUG` | `false` (production mode); `true` is contributor mode and saves uploads over the database |
| `DJANGO_SECRET_KEY` | Optional; without it a random key is created once in `.secret_key` next to the database (`/data/.secret_key` in the container) and reused |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1,[::1]`; comma-separated hostnames |
| `SQLITE_PATH` | `db.sqlite3` in the repository; `/data/db.sqlite3` in the container |
| `SITE_ALLOW_SOURCE_CHANGE` | `true` in a clone, `false` in the Docker image; enables the local [change-source page](datasets.md#your-own-dataset). Set `false` on any hosted site |
| `DATA_GOV_IN_API_KEY` | Required only by `fetch_postal_data` |
| `DJANGO_HTTPS` | `false`; `true` turns on the HTTPS redirect, HSTS (one year) and secure cookies. Only for a site served over HTTPS |
| `DJANGO_CSRF_TRUSTED_ORIGINS` | Empty; comma-separated origins such as `https://example.com` for a hosted site |
| `SITE_DEMO_UNTIL` | Empty; a date such as `2026-12-26` shows "This is a demo that runs until …" on every page |
| `SITE_REVISION` | Empty; the commit being served, reported by `/health/`. Render's `RENDER_GIT_COMMIT` is used when it is not set |
| `PORT` | `8000` in the container; hosts such as Render set it |
| `TRUST_PROXY_HTTPS` | `false`; enable only behind a trusted TLS proxy that overwrites `X-Forwarded-Proto` (see [Deploying it yourself](#deploying-it-yourself)) |

Only the bundled `db.sqlite3` is tracked; other databases and SQLite's `-wal`/`-shm` files are gitignored. Committing a refreshed `db.sqlite3` adds its full size to Git history each time.

## CI and releases

GitHub Actions runs on every push and pull request: it installs the frozen lockfile, checks formatting and lint, runs the tests, validates migrations and the OpenAPI schema, and builds the container. CI never contacts data.gov.in.

Pushing a `v*` tag makes a release, in order, and only if each step succeeds:

1. The same checks.
2. **The image:** the tag must match the version in `pyproject.toml`. The image is built for amd64 and arm64 and pushed to `ghcr.io/<owner>/<repository>` as the tag and as `latest`, with OCI labels for its source, license, version and revision.
3. **The GitHub Release:** its notes are the tag's `CHANGELOG.md` entry, and it carries `db.sqlite3`, the gzipped export (from `manage.py export_directory`) and `SHA256SUMS`.

To release a fork, set the version in `pyproject.toml`, add a `CHANGELOG.md` entry, and push the tag, for example `git tag v1.0.1 && git push origin v1.0.1`. A new package on GitHub's registry starts private; make it public under the package's settings.
