import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from django.core.exceptions import ImproperlyConfigured

from config.settings import load_secret_key

ROOT = Path(__file__).resolve().parent.parent
PRINT_SETTINGS = (
    "import json; from django.conf import settings as s; print(json.dumps({k: getattr(s, k) "
    "for k in ['DEBUG', 'SECURE_SSL_REDIRECT', 'SESSION_COOKIE_SECURE', 'CSRF_COOKIE_SECURE', "
    "'SECURE_HSTS_SECONDS', 'CSRF_TRUSTED_ORIGINS', 'ALLOW_SOURCE_CHANGE', 'SAVE_UPLOADS', "
    "'SECRET_KEY']}))"
)


def settings_with(tmp_path, **env):
    """Load settings in a fresh interpreter, isolated from this test process."""
    clean = {k: v for k, v in os.environ.items() if not k.startswith(("DJANGO_", "SITE_"))}
    clean |= {"DJANGO_SETTINGS_MODULE": "config.settings", "SQLITE_PATH": str(tmp_path / "db")}
    result = subprocess.run(
        [sys.executable, "-c", PRINT_SETTINGS],
        env=clean | env,
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(result.stdout)


def test_secret_key_is_created_once_and_reused(tmp_path):
    path = tmp_path / ".secret_key"
    key = load_secret_key(path)
    assert len(key) >= 50
    assert load_secret_key(path) == key
    if os.name != "nt":
        assert path.stat().st_mode & 0o777 == 0o600


def test_unwritable_secret_key_location_explains_the_fix(tmp_path):
    with pytest.raises(ImproperlyConfigured, match="DJANGO_SECRET_KEY"):
        load_secret_key(tmp_path / "missing" / ".secret_key")


def test_production_mode_is_the_default_and_needs_no_setup(tmp_path):
    loaded = settings_with(tmp_path)
    assert loaded["DEBUG"] is False
    # Locally, uploads work out of the box but are temporary.
    assert (loaded["ALLOW_SOURCE_CHANGE"], loaded["SAVE_UPLOADS"]) == (True, False)
    assert (loaded["SECURE_SSL_REDIRECT"], loaded["SECURE_HSTS_SECONDS"]) == (False, 0)
    assert loaded["SECRET_KEY"] == (tmp_path / ".secret_key").read_text()


def test_https_hardening_and_trusted_origins_are_opt_in(tmp_path):
    loaded = settings_with(
        tmp_path,
        DJANGO_HTTPS="true",
        DJANGO_CSRF_TRUSTED_ORIGINS="https://a.example, https://b.example",
        DJANGO_SECRET_KEY="given",
    )
    assert loaded["SECURE_SSL_REDIRECT"] and loaded["SESSION_COOKIE_SECURE"]
    assert loaded["CSRF_COOKIE_SECURE"] and loaded["SECURE_HSTS_SECONDS"] == 31536000
    assert loaded["CSRF_TRUSTED_ORIGINS"] == ["https://a.example", "https://b.example"]
    assert loaded["SECRET_KEY"] == "given"
    assert not (tmp_path / ".secret_key").exists()


def test_contributor_mode_saves_uploads(tmp_path):
    loaded = settings_with(tmp_path, DJANGO_DEBUG="true")
    assert (loaded["ALLOW_SOURCE_CHANGE"], loaded["SAVE_UPLOADS"]) == (True, True)


def test_hosting_turns_change_source_off(tmp_path):
    loaded = settings_with(tmp_path, SITE_ALLOW_SOURCE_CHANGE="false")
    assert loaded["ALLOW_SOURCE_CHANGE"] is False
    # The Docker image is for hosting, so it ships with change source off.
    assert "ENV SITE_ALLOW_SOURCE_CHANGE=false" in (ROOT / "Dockerfile").read_text()
