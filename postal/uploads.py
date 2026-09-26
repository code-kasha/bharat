"""Temporary uploads: each browser's upload lives in its own scratch SQLite file.

The bundled directory is never touched. A signed cookie names the file; the lookup page and
search read from it while the API and export keep serving the default dataset.
"""

import re
import secrets
import time
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from django.conf import settings
from django.core.signing import BadSignature
from django.db import DEFAULT_DB_ALIAS, connections
from django.db.utils import load_backend

from postal.importer import replace_dataset
from postal.models import Dataset, PostOffice

COOKIE = "dataset_upload"
SALT = "postal.uploads"
TOKEN_RE = re.compile(r"[0-9a-f]{32}")


@dataclass
class Upload:
    token: str
    path: Path
    expires: datetime


def _max_age():
    return settings.TEMPORARY_UPLOAD_HOURS * 3600


def _directory():
    return Path(settings.TEMPORARY_UPLOAD_DIR)


def _path(token):
    return _directory() / f"{token}.sqlite3"


@contextmanager
def _open(alias, name):
    """A connection private to this thread and block, so nothing outlives the request."""
    config = connections.databases[DEFAULT_DB_ALIAS] | {"NAME": name, "OPTIONS": {"timeout": 20}}
    connection = load_backend(config["ENGINE"]).DatabaseWrapper(config, alias)
    connections[alias] = connection
    try:
        yield alias
    finally:
        connection.close()
        del connections[alias]


def _unlink(path):
    try:
        path.unlink(missing_ok=True)
    except OSError:
        # Windows cannot delete a file another request still has open; a later purge will.
        pass


def cookie_token(request):
    try:
        token = request.get_signed_cookie(COOKIE, salt=SALT, max_age=_max_age())
    except (KeyError, BadSignature):
        return None
    return token if TOKEN_RE.fullmatch(token) else None


def active(request):
    """This browser's upload, or None when it has none or it has expired."""
    token = cookie_token(request)
    if token is None:
        return None
    path = _path(token)
    try:
        created = path.stat().st_mtime
    except FileNotFoundError:
        return None
    if time.time() - created > _max_age():
        _unlink(path)
        return None
    return Upload(token, path, datetime.fromtimestamp(created + _max_age(), UTC))


@contextmanager
def reading(upload):
    """Yield the database alias for lookups: the upload's, or None for the default."""
    if upload is None:
        yield None
        return
    # Read-only: a lookup can never change the upload.
    with _open(f"upload-{upload.token}", f"{upload.path.resolve().as_uri()}?mode=ro") as alias:
        yield alias


def purge(keep):
    """Delete expired uploads, then the oldest ones beyond `keep`."""
    now = time.time()
    files = []
    for path in _directory().glob("*.sqlite3*"):
        try:
            files.append((path.stat().st_mtime, path))
        except FileNotFoundError:
            continue
    fresh = []
    for created, path in sorted(files):
        if now - created > _max_age():
            _unlink(path)
        elif path.suffix == ".sqlite3":
            fresh.append(path)
    for path in fresh[: max(0, len(fresh) - keep)]:
        _unlink(path)


def store(parsed, *, source, source_period=""):
    """Write a validated upload to a new scratch file and return its token."""
    _directory().mkdir(parents=True, exist_ok=True)
    purge(keep=settings.TEMPORARY_UPLOAD_LIMIT - 1)
    token = secrets.token_hex(16)
    final = _path(token)
    # Build under another name so a reader never sees a half-written file.
    partial = final.with_suffix(".sqlite3-partial")
    try:
        with _open(f"upload-build-{token}", str(partial)) as alias:
            with connections[alias].schema_editor() as editor:
                editor.create_model(Dataset)
                editor.create_model(PostOffice)
            replace_dataset(parsed, source=source, source_period=source_period, using=alias)
        partial.replace(final)
    except BaseException:
        _unlink(partial)
        raise
    return token


def discard(token):
    if token is not None:
        _unlink(_path(token))


def set_cookie(response, token):
    response.set_signed_cookie(
        COOKIE,
        token,
        salt=SALT,
        max_age=_max_age(),
        httponly=True,
        samesite="Lax",
        secure=settings.HTTPS,
    )
