# Contributing to Bharat

Thanks for looking. A quick word on where things stand, then how to share what you make.

## The project is finished

As of v1.0.0, Bharat is complete and is not actively maintained. It works as-is, and no further updates are planned. Issues and pull requests are welcome, but they may go unanswered. Please don't wait on a reply: fork it, reuse it and grow it in whatever direction you need.

## License

The code is under the [MIT License](LICENSE), with no extra conditions. Use it, change it, host it or sell it. The license only asks that its notice stays with copies of the code.

Data fetched from data.gov.in is published under the Government Open Data License – India; keep its attribution requirements when you redistribute it.

A mention of Bharat in your project is appreciated, never required.

## Sharing an updated dataset

If you load a newer or better directory, others can probably use it too. Please share it back.

1. Run Bharat in contributor mode, so the upload is saved: `DJANGO_DEBUG=true uv run python manage.py runserver` (on Windows PowerShell, `$env:DJANGO_DEBUG="true"` first).
2. Upload your CSV or JSON file on the [change-source page](http://127.0.0.1:8000/source/). Say where it came from, and give its date if you know it; never guess one.
3. The page then shows a **Share this dataset** note with the git commands to commit `db.sqlite3` on a branch, and a ready-made description.
4. Then either:
   - **open a pull request** on this repository with that description, or
   - **publish your fork** with the updated `db.sqlite3` and the same details in its README.

Both are equally good. Pull requests may not be reviewed, so a published fork is often the quickest way to make your dataset available.

Whichever you choose, include:

- [ ] the source: a link, or who provided the data and how
- [ ] the source date, an approximate period, or "not recorded"
- [ ] the office count, and how many offices are listed more than once
- [ ] the SHA256 shown on the page

## Changing the code

Use Python 3.13 and [uv](https://docs.astral.sh/uv/):

```sh
uv sync --frozen
uv run ruff check . && uv run ruff format --check .
uv run pytest
uv run python manage.py makemigrations --check --dry-run
uv run python manage.py spectacular --validate --fail-on-warn --file schema.yml
```

[`AGENTS.md`](AGENTS.md) lists the rules the code keeps, for example that a PIN may map to many offices, that imports are fully validated before anything changes, and that the lookup page costs one HTTP request. Tests use synthetic data and never reach the network.
