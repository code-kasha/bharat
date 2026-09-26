# bharat-post-dir – work index (written 26 September 2026)

Pick up from here. Nothing below is started unless marked done.

## How to resume (for any session, local or cloud)

- Work on the branch **`release-v1`** (pushed to GitHub). Do not work on `main`.
- When the user says "let's continue", show this task list with its status (done / next / remaining), then propose the next task with its size (small / medium / large) and wait for a go.
- Go **one task at a time** and **ask before expensive steps**: browser sessions, Docker builds and runs, benchmarks, large rewrites, web research. Prefer unit tests and targeted checks. Keep replies short.
- Treat "Decisions already made" as settled; do not re-ask them.
- After each task: run the checks from `AGENTS.md`, commit on `release-v1`, and mark the task DONE here.

## Current state (updated 26 September 2026)

- The repository is **`code-kasha/bharat-post-dir`** (renamed from `code-kasha/bharat`; GitHub redirects the old name). `main` has the v1.0.0 release (tag `v1.0.0` on `e1b03a4`). Follow-up work goes on **`release-v1`**, restarted from `main`, through a pull request.
- **Tasks 1–15 are done:** v1.0.0 is released, the image is public, and the demo is live until 26 December 2026. Left: task 17 (write-up link, when it is published) and task 16 (shutdown on 26 December 2026; a reminder is set).
- Checks: 119 tests pass; lint, format, migrations and the OpenAPI schema are clean; CI is green on every `release-v1` push.
- Cloud environment notes: the network policy allows `pkg-containers.githubusercontent.com` (GHCR image layers) and `cdn.jsdelivr.net` (Swagger UI), added by the user. Docker Hub rate-limits anonymous pulls from the sandbox; pull through `mirror.gcr.io` there. The sandbox browser does not trust the proxy certificate.
- `TODO.md` is committed on `release-v1` so any session can read it. Whether to keep it after v1.0.0 is undecided (ask).
- The README intro links the write-up at `http://localhost:3000/projects/bharat-post-dir` until it is published (task 17).

## Decisions already made

- **v1.0.0 is a finished seed, not a maintained project.** Publish it complete and honest, with a note on what it does; anyone may take it and grow it. No ongoing updates are planned after v1.0.0.
- **Completely free to use:** MIT, no accounts, API keys, paid tiers, ads or tracking for anyone using the code, the image, the data or the demo.
- **Production mode (`DEBUG=false`) is the default everywhere**, including `runserver` and Docker. Contributor mode is opt-in with `DJANGO_DEBUG=true`.
- **Docker is for hosting.** It runs in production mode on a real server and domain.
- **Hosted site: change source is off** (`SITE_ALLOW_SOURCE_CHANGE=false` in the production config). The docs must say: to use your own dataset, **run it locally or deploy it yourself**.
- **Local clone, default mode:** uploads are **temporary**. They affect only that browser (web page and search); `db.sqlite3` is untouched. Provide "Back to the default dataset".
- **Local clone, `DJANGO_DEBUG=true`:** uploads **replace `db.sqlite3`**, then show a note asking the user to open a PR to share the dataset.
- **Conflicting duplicates are always kept** (government data; duplicates can be legitimate). Report how many offices are listed more than once. Exact identical rows are still merged. Applies to uploads and to `fetch_postal_data`.
- **Uploads accept CSV and all JSON shapes:** bharat-post-dir's export (`{"dataset", "offices"}`, prefills source/date), the data.gov.in API response (`{"records": [...]}`), and a plain list of offices (CSV column names or bharat-post-dir field names).
- **License and contributions:** MIT, no extra constraints. If you update the dataset, please share it back: open a PR **or publish your fork** (PRs may not be reviewed). A mention is appreciated, never required (friendly tone).
- **Repository name:** rename `code-kasha/bharat` to `code-kasha/bharat-post-dir`, on GitHub and everywhere it is referenced (task 10).
- **Naming (decided 26 September 2026):** the project is called `bharat-post-dir` wherever people read its name (pages, docs, API title). Technical names are generic: `SITE_ALLOW_SOURCE_CHANGE`, cookie `dataset_upload`, `/data/db.sqlite3`, export `post-offices-….json`, containers `app`/`app-demo`, volume `app-data`, network `app-net`. Django packages stay `config` and `postal`. The README has no name heading; it starts with the description.
- **First release is `v1.0.0`**, published only after everything else is done.
- **Hosting: a free-tier service with a planned end date** (task 15), then a planned shutdown (task 16). The exact platform and end date are chosen at deploy time.
- **Community files stay minimal:** nothing that promises ongoing support (no `SECURITY.md` with response times, no changelog beyond 1.0). Issues stay open with a note that they may go unanswered.
- **Decide later:** archiving the repository after release (read-only and still forkable, but it blocks dataset PRs), and GitHub Discussions.

## Tasks

1. **Production mode by default** — DONE (`release-v1`). Docs for it land in task 7.
   - `DJANGO_DEBUG` default `false`. With no `DJANGO_SECRET_KEY`, generate one on first run and persist it next to the database (gitignored, e.g. `.secret_key`, or `/data/.secret_key` in the container). Never commit it.
   - HTTPS redirect, HSTS and secure cookies only when explicitly enabled (e.g. `DJANGO_HTTPS=true`), so `http://localhost` works in production mode.
   - Add `DJANGO_CSRF_TRUSTED_ORIGINS` for the hosted domain. Check error pages and the Swagger UI (CDN assets) with `DEBUG=false`.
   - Update `.env.example`: it still sets `DJANGO_DEBUG=true`. Deliberately left until this task, because switching it earlier breaks anyone using it.
2. **Temporary uploads (production mode, local)** — DONE (`release-v1`). `postal/uploads.py`: one scratch SQLite file per browser under `.uploads/` next to the database, signed HTTP-only cookie, 24-hour expiry, at most 5 kept (oldest deleted first), 100 MB upload cap. Change source is now on by default in a clone; the Dockerfile sets `SITE_ALLOW_SOURCE_CHANGE=false` because the image is for hosting. README "Changing the source" and AGENTS.md updated; full docs remain task 7.
   - Store each upload in its own scratch SQLite file under a temp/data directory, keyed by a signed cookie. Expire and delete after a set time; cap the size.
   - The lookup page and search read from it; the source label shows the uploaded file's details. The API and export keep serving the default dataset.
   - "Back to the default dataset" button. Keep one request per page.
3. **Saving uploads (`DJANGO_DEBUG=true`)** — DONE (`release-v1`). The note is on `/?updated=1` after a saved upload; the repository URL is `REPOSITORY_URL` in settings (update it in task 10). `replace_dataset` now checkpoints the WAL so a committed `db.sqlite3` is complete.
   - Keep the current replace-`db.sqlite3` behaviour.
   - After success, show a "Share this dataset" note: git commands (branch, commit `db.sqlite3`), a link to open a PR on `code-kasha/bharat-post-dir` **or publish your fork**, and a pre-filled description (source, date or period, office count, SHA256). Say plainly that the PR may not be reviewed.
   - Temporary uploads show a lighter note: run with `DJANGO_DEBUG=true` to save and share it.
4. **Keep conflicting duplicates** — DONE (`release-v1`). `Dataset.repeated_identity_count` (generated migration 0005, data migration 0006 fills it from existing rows). Bundled `db.sqlite3` migrated: office rows byte-identical, count = 3. Verified by exporting the bundled 155,599 rows to CSV and uploading them in contributor mode: all loaded, 3 repeated offices kept.
   - Importer: stop rejecting conflicting identities; count offices listed more than once (e.g. `repeated_identity_count` on `Dataset`, via a generated migration) and show it on the page, the API and the upload result.
   - Update tests that expect rejection. Re-upload the original 155,599-row file to confirm it now loads (it has 3 such offices).
   - Update the AGENTS.md invariant ("reject conflicting office identities").
5. **JSON uploads** — DONE (`release-v1`). `importer.parse_upload` detects CSV or JSON from content; bharat-post-dir field names are accepted as aliases everywhere. Verified with the full 43 MB export uploaded back (source left empty, provenance carried over).
    detect the format from content; support the three shapes above; same validation and line/record-numbered errors; tests for each shape.
6. **Contributing and license** — DONE (`release-v1`). `CONTRIBUTING.md` added; README "License" became "Contributing and license".
   - Add `CONTRIBUTING.md`: the project is finished and not actively maintained; MIT, no constraints; fork freely; how to share an updated dataset (PR with `db.sqlite3` and its source details, or publish your fork); a mention is appreciated.
   - Add a README "Contributing and license" section linking it.
7. **Docs** — DONE (`release-v1`). README: production mode by default and contributor mode per shell, full configuration table, Docker image notes, a new "Deploying it yourself" section (app container on a private network, Caddy, backups, updates, rollback, Django 5.2 support to April 2028). AGENTS.md updated. Performance numbers unchanged: lookup still one request and 3 queries. The deploy steps are verified in task 8.
   - README: production-by-default, "run it locally or deploy it yourself to use your own dataset", the temporary vs saved upload behaviour, duplicates kept, JSON formats.
   - A production deployment section: `docker run` with the production env vars, a persistent `/data` volume, a reverse proxy for TLS (Caddy example), `DJANGO_ALLOWED_HOSTS`, `DJANGO_CSRF_TRUSTED_ORIGINS`, HTTPS flags, backups, updates and rollback.
   - Refresh AGENTS.md and the performance/request-count numbers if anything changes.
   - State the one known expiry: Django 5.2's security support ends in April 2028; a fork should upgrade Django before running it publicly after that.
8. **Deploy once with Docker (verification)** — DONE in the cloud sandbox (`localhost` + Caddy local CA). Everything in the README steps passed. Found and fixed one README bug: the rollback restore ran as root and left `bharat.sqlite3` unwritable by `appuser`; it now restores with the bharat-post-dir image. Sandbox-only workarounds (not in the repo): a `mirror.gcr.io` registry mirror (Docker Hub 429), `pkg-containers.githubusercontent.com` allowed in the environment's network settings, and a build with `--network host` + the proxy CA mounted only for `uv sync`. Needs a real domain to verify: public certificate issuance and renewal, DNS, firewall. **Local run: DONE on 26 September 2026** (Windows 11, Docker Desktop, Engine 29.8.0, Caddy 2, no workarounds): every checklist item passed, including unknown hosts refused, restart, backup (integrity ok) and rollback (database owned and writable by `appuser`). Recorded in `docs/deployment.md`.
   - Local checklist (Docker Desktop, no workarounds): first `git fetch origin && git switch release-v1 && git pull` (the repository is now `code-kasha/bharat-post-dir`; update an old clone with `git remote set-url origin https://github.com/code-kasha/bharat-post-dir.git`). Then `docker build -t bharat-post-dir:local .` and steps 1–4 of `docs/deployment.md` "Deploying it yourself", with `localhost` for the domain (`DJANGO_ALLOWED_HOSTS=localhost`, `DJANGO_CSRF_TRUSTED_ORIGINS=https://localhost`, Caddyfile site `localhost`). Open `https://localhost/` (accept or trust Caddy's local certificate): the heading reads bharat-post-dir, search `110001` gives 23 results, `/health/` is ok, `/api/v1/dataset/` shows 155599 offices and 3 repeated, `/source/` is 404, `/api/docs/` loads, and `/api/v1/export/` downloads `post-offices-undated-959693b760df.json`. Then `docker restart app` (data kept), and try the backup and rollback commands. On Windows, run the multi-line commands in Git Bash or put them on one line. Record the result here and in `docs/deployment.md`'s verification note.
   - No server or domain is available, so run the image exactly as the README's production instructions say: production mode, a volume, and a local Caddy proxy with HTTPS in front.
   - Check the lookup page, search, export, health, that `/source/` is off, and that data survives a restart. Report anything that needs a real domain to verify.
9. **Checkpoint** — DONE. All checks passed locally (113 tests at the time; 119 now); CI green on every `release-v1` push through `3d529df`. README validation notes updated. CI runs on every push and pull request.
10. **Rename the repository to `bharat-post-dir`** — DONE. Renamed on GitHub by the user; references updated (README clone URL, folder and image names, `REPOSITORY_URL`, `pyproject.toml` and regenerated `uv.lock`). Kept on purpose: container name `bharat`, volume `app-data` (renaming would orphan existing data), Django packages. The "memory note" lives outside this repository; update it on the machine that has it. (confirm with the user right before running it; it is public-facing)
   - `gh repo rename bharat-post-dir`; update the local `origin` remote. GitHub redirects old URLs, but update every reference anyway.
   - References to update: README clone URL and links, the PR link in the "Share this dataset" note, `pyproject.toml` name, Docker image names in docs (`bharat:local` to `bharat-post-dir:local`), `ghcr.io/code-kasha/bharat-post-dir` (CI derives it from the repo name), AGENTS.md, CONTRIBUTING.md and the memory note.
   - Keep the internal Django package names (`config`, `postal`) as they are.
11. **Screenshots** — DONE. In `docs/images/` (all under 125 KB): `home-light.png`, `home-dark.png`, `search-delhi.png`, `phone.png`, `change-source.png`, `share-dataset.png`, `social-preview.png` (1280×640, for GitHub Settings → Social preview; the user uploads it). README hero added with `<picture>`. Screenshots found and fixed two UI issues: the data panel squeezed its values on phones (now stacks under 40rem), and counts now show thousands separators (155,599). `api-docs.png` taken after `cdn.jsdelivr.net` was allowed (the sandbox browser does not trust the proxy CA, so the pinned Swagger files were fetched with verified curl and served to the page). Alt text for task 12:
   - `search-delhi.png`: "Search results for Delhi: 544 results, page 1 of 22, in a table of office, PIN, district, state, type, delivery and division."
   - `phone.png`: "The lookup page on a phone: the data panel's labels and values stacked, the search box with 110001, and the start of 23 results."
   - `change-source.png`: "The change-source page: a CSV or JSON file, its source, an exact or approximate source date, and an 'Upload and use in this browser' button, with a note that the upload is temporary."
   - `share-dataset.png`: "The 'Share this dataset' note after a saved upload: git commands to commit db.sqlite3 on a branch, and a ready-made description with source, date, office count and SHA256."
   - `api-docs.png`: "The API documentation (Swagger UI): the bharat-post-dir API's read-only GET endpoints for the dataset, districts, the export, offices, PIN codes and states."
   - `social-preview.png`: "bharat-post-dir: which India Post offices sit behind a PIN code or place name. 155,599 offices, lookup page, JSON API, one-file export, Docker and SQLite."
   - Home page (light and dark), "Delhi" search results, phone view, change-source page, "Share this dataset" note, API docs.
   - Save under `docs/images/`, compress to about 200 KB or less each, with alt text. The README hero uses `<picture>` to follow the reader's light or dark theme.
   - Make a 1280×640 social preview image. The user uploads it in GitHub Settings → Social preview (there is no API for it).
12. **README rewrite and `docs/`** — DONE. README starts with the description (no name heading), then badges (CI, MIT, Python 3.13, Django 5.2 LTS), links, the hero, highlights and status, following the outline below. Long material is in `docs/api.md`, `datasets.md`, `deployment.md`, `docker-windows.md` and `performance.md`; all Markdown links and anchors checked. **Still to add after tasks 14–15:** latest-release and container-image badges, and the demo link with its end date.
   - No name heading (decided): the README starts directly with the description. Opening line (draft; the user may reword): "A helper that tells you which India Post offices sit behind a PIN code or place name, ready to drop into your own applications as a JSON API or a Docker image."
   - Right after it, a highlights list of what we built:
     - 155,599 offices bundled; works right after cloning.
     - Accessible lookup page, one request per page, no JavaScript.
     - JSON API with OpenAPI docs.
     - The whole directory in one download (1.4 MB gzipped) that is never resent unchanged.
     - Every page shows where the data came from and how current it is.
     - Bring your own dataset (CSV or JSON) and share it back.
     - Ready-to-run Docker image for your own deployment; SQLite, no external services.
   - A status note near the top: "Complete as of v1.0.0 and not actively maintained. It works as-is; fork it, reuse it, grow it."
   - Outline:
     - Header with badges (CI, license, Python, Django, latest release, container image) and links (live demo with its end date, API docs, dataset download, contributing).
     - Hero screenshot, then the highlights.
     - Quick start: clone, then run with Python or Docker.
     - Using it: lookup page, API with `curl` examples, whole-directory download.
     - Use in your application: the Docker image, the API, the export.
     - Your own dataset.
     - The data: provenance, fields, known quirks.
     - Deploy it yourself.
     - For developers.
     - Where this could go: ideas for whoever picks it up (monthly auto-refresh from data.gov.in with a data changelog, a static JSON API on GitHub Pages or a CDN, npm and PyPI lookup packages, a per-release data quality report, resolving the bundled data's origin and license).
     - Contributing, license and credit.
   - Move long material into `docs/`: `deployment.md`, `docker-windows.md`, `api.md`, `datasets.md`, `performance.md`.
13. **Repository settings** — DONE. Set by the user and verified through the GitHub API: description, 15 topics, wiki off, Discussions off, website empty (set in task 15). Social preview uploaded by the user (not visible through the API). PR template (dataset checklist) and issue template (may go unanswered) committed in `.github/`; they take effect once merged into `main`.
   - Description (draft): "Indian PIN code and post office directory: 155,599 offices, a one-request lookup page, JSON API and one-file export. Django + SQLite; bring your own dataset."
   - Topics: `india`, `pincode`, `pin-code`, `postal-code`, `post-office`, `india-post`, `open-data`, `government-data`, `dataset`, `rest-api`, `openapi`, `django`, `django-rest-framework`, `sqlite`, `python`.
   - Website: set in task 15 to the demo URL; cleared in task 16.
   - Community files, minimal: a PR template with a dataset checklist (source, date, SHA256), an issue template noting issues may go unanswered, and turn off the empty wiki. No `SECURITY.md` promising response times. Discussions: decide later.
14. **Release `v1.0.0` and the container package** — RELEASED on 26 September 2026: PR code-kasha/bharat-post-dir#1 merged (`e1b03a4`), tag `v1.0.0` pushed from the user's machine (this cloud session's git proxy refuses tag pushes with 403), and the tag run passed all three jobs: image `ghcr.io/code-kasha/bharat-post-dir:v1.0.0` + `latest` (amd64, arm64) and the GitHub Release with `db.sqlite3`, the export and `SHA256SUMS` (asset digests match the local dry run). Follow-up on `release-v1`: CI actions updated to their latest Node 24 releases, uv 0.12.19, runner pinned to `ubuntu-24.04` (no deprecation or migration notices), README release/container badges and the published-image instructions. Follow-up merged as code-kasha/bharat-post-dir#2 (`f678c51`). The GHCR package is public: an anonymous pull of `v1.0.0` and `latest` works, with linux/amd64 and linux/arm64 and the description, license and source annotations. **Task 14 DONE.**
   - Set the version to 1.0.0 in `pyproject.toml` and the OpenAPI settings; write the release notes (a single `CHANGELOG.md` entry for 1.0.0 at most).
   - Extend the tag-triggered CI job: create the GitHub Release after all checks pass, attaching `db.sqlite3`, the gzipped JSON export and `SHA256SUMS`.
   - Publish `ghcr.io/code-kasha/bharat-post-dir` as `v1.0.0` and `latest`, for amd64 and arm64, with OCI labels linking the repository, license and description. Make the package public.
   - No PyPI package: bharat-post-dir is an application, not a library.
15. **Deploy the demo on a free tier, with a planned end date** — DONE on 26 September 2026. Live at https://bharat-post-dir.onrender.com/ on Render's free tier until **26 December 2026** (chosen because Cloud Run needs a billing card and Hugging Face Docker Spaces need a paid plan). Every page shows the end date (`SITE_DEMO_UNTIL`). CI's `deploy` job (`production` environment) triggers `secrets.DEPLOY_HOOK_URL` after the checks on each push to `main` and waited until `/health/` reported `29128d3` (run 36237065532, attempt 7). `DEMO_URL` is a repository variable; the repository website is set to the demo. `onrender.com` is blocked in this cloud environment, so check the site from a browser.
   - The hosted demo is read-only (change source is off), so the data can stay baked into the image: no persistent disk is needed, which widens the free-tier choices. The generated secret key may live on the container's temporary disk.
   - Candidates to check at deploy time (free tiers change often; verify current terms, limits and that no card or paid plan is required): Render free web service, Koyeb, Google Cloud Run, Hugging Face Spaces (Docker). Cold starts after idle are acceptable for a demo.
   - Use the provider's free subdomain (no domain costs). No ads or analytics.
   - Pick the end date with the user. Show it in the README ("Demo available until …") and on the site.
   - Add a CI deploy job using a `production` environment with its URL, so it appears in the repository's Deployments sidebar; check `/health/` after deploying.
   - Set the repository website to the demo URL.
16. **Planned shutdown at the end date**
   - Stop and delete the service, clear the repository website field, and change the README demo line to "The demo ran until …; run it yourself with Docker or Python."
   - Reminder SET: a Claude routine "Shut down the bharat-post-dir demo" fires on 26 December 2026 at 03:30 UTC (09:00 IST) with push and email notifications (trigger `trig_01SMVCrqu6EDJWDgjSnvtGpq`). The session it starts has no repository or GitHub tools attached, so treat it as the reminder; do the shutdown in a session on `code-kasha/bharat-post-dir`. Also turn off the CI `deploy` job (remove it, or delete `vars.DEMO_URL` and `secrets.DEPLOY_HOOK_URL`).
17. **After deployment: the write-up link.** The README intro links `http://localhost:3000/projects/bharat-post-dir`, which only works on your machine. Once the write-up is published, replace it with the public URL (or remove the link).

## Stale items

Resolved on 26 September 2026:

- Done: removed `output` (legacy CLI folder) from `.gitignore` and `.dockerignore`.
- Done: removed `staticfiles/` from `.gitignore`.
- Done: deleted the merged local branch `sqlite-directory`.
- Done: deleted the leftover Docker image `bharat:local`.
- Moved to task 1: `.env.example` still sets `DJANGO_DEBUG=true`.
- Moved to task 17: replace the local write-up link after deployment.
- Undecided: whether to delete this `TODO.md` once everything is done. Do not delete it without asking.

## Order

~~Commit the current work~~ (done, `efc1544`) → tasks 1–8 → checkpoint (task 9) → rename (10) → screenshots (11) → README and `docs/` (12) → repository settings (13) → release `v1.0.0` (14) → deploy the free-tier demo with an end date (15) → the write-up link (17) → planned shutdown at the end date (16).
