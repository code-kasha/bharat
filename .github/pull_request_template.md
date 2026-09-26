<!--
bharat-post-dir is complete and not actively maintained, so this pull request may not be reviewed.
Publishing your fork works just as well. Thank you for sharing!
-->

## What this changes

<!-- One or two sentences. -->

## If it updates the dataset (`db.sqlite3`)

The "Share this dataset" note on the lookup page, shown after a saved upload, fills most of this in.

- [ ] Source: a link, or who provided the data and how
- [ ] Source date, an approximate period, or "not recorded" (never a guess)
- [ ] Office count, and how many offices are listed more than once
- [ ] SHA256 shown on the page

## If it changes code

- [ ] `uv run ruff check .` and `uv run ruff format --check .`
- [ ] `uv run pytest`
- [ ] `uv run python manage.py makemigrations --check --dry-run`
- [ ] `uv run python manage.py spectacular --validate --fail-on-warn --file schema.yml`
