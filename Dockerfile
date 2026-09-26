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
ENV SQLITE_PATH=/data/bharat.sqlite3
USER appuser
EXPOSE 8000
CMD ["sh", "-c", "/app/.venv/bin/python manage.py migrate --noinput && exec /app/.venv/bin/gunicorn config.wsgi:application --bind 0.0.0.0:8000 --workers 2 --access-logfile -"]
