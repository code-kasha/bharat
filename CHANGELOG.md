# Changelog

## 1.0.0 (2026-09-26)

The first and final planned release. bharat-post-dir is complete as of this version and not actively maintained; fork it freely.

- **The directory:** 155,599 India Post offices bundled in `db.sqlite3` (the maintainer-verified 2023 snapshot, source date on or before June 2023), ready right after cloning.
- **Lookup page:** search by PIN, office or district in one HTTP request per page, with no JavaScript. Accessible, in light and dark, and usable on phones. Every page shows the data's source, date, load time and office count.
- **JSON API:** read-only PIN lookup, search, state and district listings and dataset provenance, with OpenAPI docs at `/api/docs/`.
- **Whole-directory download:** `/api/v1/export/` streams every office in one request, 1.4 MB gzipped, versioned by SHA256 and never resent unchanged. `manage.py export_directory` writes the same file.
- **Your own dataset:** upload CSV or JSON (the official layout, a data.gov.in response, a list of offices, or an export). Uploads are validated in full first. They are temporary and private to one browser by default, or saved with `DJANGO_DEBUG=true`, with a note on sharing them back. Offices listed more than once are kept and counted.
- **Official data:** `fetch_postal_data` loads the Department of Posts' directory from data.gov.in with an API key.
- **Deployment:** production mode by default, and a Docker image (amd64 and arm64) built for hosting, with steps for running it behind Caddy, backups, updates and rollback.

Release assets: `db.sqlite3`, the gzipped export and `SHA256SUMS`. Container image: `ghcr.io/code-kasha/bharat-post-dir:v1.0.0` (also `latest`).
