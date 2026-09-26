FROM python:3.13-slim
COPY --from=ghcr.io/astral-sh/uv:0.12.17 /uv /usr/local/bin/uv
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev
COPY config ./config
COPY postal ./postal
COPY manage.py ./manage.py
RUN useradd --create-home appuser && mkdir /data && chown appuser /data
ENV SQLITE_PATH=/data/bharat.sqlite3
VOLUME /data
USER appuser
EXPOSE 8000
CMD ["/app/.venv/bin/gunicorn", "config.wsgi:application", "--bind", "0.0.0.0:8000", "--workers", "2", "--access-logfile", "-"]
