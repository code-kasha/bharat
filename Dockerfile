FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY config ./config
COPY postal ./postal
COPY manage.py ./manage.py
RUN useradd --create-home appuser
# SQLite needs a writable directory for its WAL files, not just a writable database file.
COPY --chown=appuser db.sqlite3 /data/bharat.sqlite3
RUN chown appuser /data
# The venv on PATH keeps `docker exec <name> python manage.py ...` free of absolute paths,
# which some host shells (e.g. Git Bash) would otherwise rewrite.
ENV SQLITE_PATH=/data/bharat.sqlite3 PATH=/app/.venv/bin:$PATH
# The image is for hosting, where the unauthenticated change-source page must stay off.
ENV BHARAT_ALLOW_SOURCE_CHANGE=false
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "python manage.py migrate --noinput && exec gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --access-logfile -"]
