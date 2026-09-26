import os
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from django.core.management.utils import get_random_secret_key


def env_flag(name, default=False):
    return os.environ.get(name, str(default)).lower() == "true"


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


def load_secret_key(path):
    """Create a random key on first run and reuse it, so production mode needs no setup."""
    try:
        descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    except FileExistsError:
        return Path(path).read_text().strip()
    except OSError as exc:
        raise ImproperlyConfigured(f"Cannot create {path}; set DJANGO_SECRET_KEY instead.") from exc
    key = get_random_secret_key()
    with os.fdopen(descriptor, "w") as stream:
        stream.write(key)
    return key


BASE_DIR = Path(__file__).resolve().parent.parent
# Production mode is the default; DJANGO_DEBUG=true is contributor mode.
DEBUG = env_flag("DJANGO_DEBUG")
DATABASE_PATH = Path(os.environ.get("SQLITE_PATH", BASE_DIR / "db.sqlite3"))
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY") or load_secret_key(
    DATABASE_PATH.parent / ".secret_key"
)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]")
CSRF_TRUSTED_ORIGINS = env_list("DJANGO_CSRF_TRUSTED_ORIGINS")
INSTALLED_APPS = ["django.contrib.contenttypes", "rest_framework", "drf_spectacular", "postal"]
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]
ROOT_URLCONF = "config.urls"
# The change-source page has no authentication, so it is for local use; hosted sites
# (including the Docker image) set SITE_ALLOW_SOURCE_CHANGE=false.
ALLOW_SOURCE_CHANGE = env_flag("SITE_ALLOW_SOURCE_CHANGE", True)
SOURCE_UPLOAD_MAX_BYTES = 100 * 1024 * 1024
# Contributor mode saves an upload over the database. Otherwise each upload is temporary: a
# scratch SQLite file that only the uploading browser reads, deleted after a set time.
SAVE_UPLOADS = DEBUG
TEMPORARY_UPLOAD_DIR = DATABASE_PATH.parent / ".uploads"
TEMPORARY_UPLOAD_HOURS = 24
TEMPORARY_UPLOAD_LIMIT = 5
# Where saved datasets can be shared back (the "Share this dataset" note).
REPOSITORY_URL = "https://github.com/code-kasha/bharat-post-dir"
WSGI_APPLICATION = "config.wsgi.application"
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    }
]
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": DATABASE_PATH,
        "OPTIONS": {
            # WAL lets API reads continue while an import writes; IMMEDIATE serializes writers.
            "init_command": "PRAGMA journal_mode=WAL; PRAGMA synchronous=NORMAL;",
            "transaction_mode": "IMMEDIATE",
            "timeout": 20,
        },
    }
}
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [],
    "UNAUTHENTICATED_USER": None,
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.AllowAny"],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 25,
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
}
SWAGGER_UI_VERSION = "5.33.0"
SPECTACULAR_SETTINGS = {
    "TITLE": "bharat-post-dir API",
    "DESCRIPTION": "Read-only postal lookup. Provenance is available at /api/v1/dataset/.",
    "VERSION": "0.3.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Pin the docs page's CDN assets: drf-spectacular defaults to @latest, which changes unseen.
    "SWAGGER_UI_DIST": f"https://cdn.jsdelivr.net/npm/swagger-ui-dist@{SWAGGER_UI_VERSION}",
    "SWAGGER_UI_FAVICON_HREF": (
        f"https://cdn.jsdelivr.net/npm/swagger-ui-dist@{SWAGGER_UI_VERSION}/favicon-32x32.png"
    ),
}
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
# HTTPS hardening is opt-in so production mode also works on http://localhost.
HTTPS = env_flag("DJANGO_HTTPS")
SECURE_SSL_REDIRECT = HTTPS
SESSION_COOKIE_SECURE = HTTPS
CSRF_COOKIE_SECURE = HTTPS
SECURE_HSTS_SECONDS = 31536000 if HTTPS else 0
# Enable only behind a proxy that strips client-supplied forwarding headers.
if env_flag("TRUST_PROXY_HTTPS"):
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
