"""
Django settings for the Corporate Expense Intelligence backend.

All secrets and environment-specific values are read from environment
variables (loaded from backend/.env). Nothing sensitive is hard-coded here.
See backend/.env.example for the full list.
"""

import os
import sys
from datetime import timedelta
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent

# Load backend/.env into os.environ. Real environment variables take precedence.
load_dotenv(BASE_DIR / ".env")


# ---------------------------------------------------------------------------
# Environment helpers
# ---------------------------------------------------------------------------
def env_required(name):
    """Return a required env var or stop startup with a clear message."""
    value = os.environ.get(name)
    if not value:
        raise ImproperlyConfigured(
            f"Environment variable {name} is not set. "
            f"Copy backend/.env.example to backend/.env and fill it in."
        )
    return value


def env_str(name, default=""):
    return os.environ.get(name, default)


def env_bool(name, default=False):
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_int(name, default):
    return int(os.environ.get(name, default))


def env_list(name, default=""):
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# ---------------------------------------------------------------------------
# Core security
# ---------------------------------------------------------------------------
SECRET_KEY = env_required("DJANGO_SECRET_KEY")
DEBUG = env_bool("DEBUG", False)
ALLOWED_HOSTS = env_list("ALLOWED_HOSTS", "127.0.0.1,localhost")


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt.token_blacklist",  # stores issued/blacklisted refresh tokens
    "corsheaders",
    "django_filters",
]

LOCAL_APPS = [
    "common",
    "accounts",
    "vendors",
    "invoices",
    "fraud",
    "approvals",
    "audit",
    "notifications",
    "system_settings",
    "reports",
    "demo",
]

# Custom user model. Must be set before the first migration.
AUTH_USER_MODEL = "accounts.User"

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",  # must be as high as possible
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


# ---------------------------------------------------------------------------
# Database: PostgreSQL only
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env_required("DATABASE_NAME"),
        "USER": env_required("DATABASE_USER"),
        "PASSWORD": env_required("DATABASE_PASSWORD"),
        "HOST": env_str("DATABASE_HOST", "127.0.0.1"),
        "PORT": env_str("DATABASE_PORT", "5432"),
        "CONN_MAX_AGE": 60,
        "OPTIONS": {"connect_timeout": 5},
    }
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"


# ---------------------------------------------------------------------------
# Passwords
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]


# ---------------------------------------------------------------------------
# Internationalisation
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = env_str("TIME_ZONE", "UTC")  # server timezone; business hours timezone is a SystemSetting
USE_I18N = True
USE_TZ = True  # store timestamps in UTC, convert for display


# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"


# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    # Secure by default: every endpoint requires login unless it opts out.
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    # The API is stateless: every request carries "Authorization: Bearer <access token>".
    # No session cookies means no CSRF exposure for API calls.
    "DEFAULT_AUTHENTICATION_CLASSES": ["rest_framework_simplejwt.authentication.JWTAuthentication"],
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"]
    + (["rest_framework.renderers.BrowsableAPIRenderer"] if DEBUG else []),
    "DEFAULT_PAGINATION_CLASS": "common.pagination.StandardPagination",
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "common.filters.NullsLastOrderingFilter",
    ],
    "EXCEPTION_HANDLER": "common.exceptions.custom_exception_handler",
    # Brute-force protection for the login endpoint (views opt in with throttle_scope).
    "DEFAULT_THROTTLE_RATES": {"login": env_str("LOGIN_RATE_LIMIT", "10/min")},
}


# ---------------------------------------------------------------------------
# JWT (djangorestframework-simplejwt), see docs/authentication.md
# ---------------------------------------------------------------------------
SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=env_int("JWT_ACCESS_MINUTES", 30)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=env_int("JWT_REFRESH_DAYS", 1)),
    "ROTATE_REFRESH_TOKENS": True,       # each refresh returns a new refresh token...
    "BLACKLIST_AFTER_ROTATION": True,    # ...and the old one can never be used again
    "UPDATE_LAST_LOGIN": False,          # our login view updates it (and writes an audit entry)
    "ALGORITHM": "HS256",
    "SIGNING_KEY": env_required("JWT_SIGNING_KEY"),  # separate from DJANGO_SECRET_KEY
    "AUTH_HEADER_TYPES": ("Bearer",),
}


# ---------------------------------------------------------------------------
# CORS: only the React dev server may call the API from a browser
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = env_list("CORS_ALLOWED_ORIGINS", "http://localhost:5173")
# Let the browser read the filename of CSV/PDF downloads.
CORS_EXPOSE_HEADERS = ["Content-Disposition", "X-Report-Rows", "X-Report-Truncated"]


# ---------------------------------------------------------------------------
# HTTPS hardening (docs/deployment.md). Off for local http://127.0.0.1 development;
# set HTTPS=True when the site is served over TLS (python manage.py check --deploy is then clean).
# ---------------------------------------------------------------------------
if env_bool("HTTPS", False):
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = env_int("HSTS_SECONDS", 3600)   # start small; raise once HTTPS is confirmed everywhere
    SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool("HSTS_INCLUDE_SUBDOMAINS", False)
    # Behind a reverse proxy that terminates TLS (IIS, nginx), trust its X-Forwarded-Proto header.
    if env_bool("BEHIND_PROXY", False):
        SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


# ---------------------------------------------------------------------------
# File uploads (CSV / JSON invoice import)
# ---------------------------------------------------------------------------
IMPORT_MAX_FILE_BYTES = env_int("IMPORT_MAX_FILE_BYTES", 2 * 1024 * 1024)  # 2 MB
IMPORT_MAX_ROWS = env_int("IMPORT_MAX_ROWS", 1000)


# ---------------------------------------------------------------------------
# Sensitive data
# Bank account numbers are never stored; only last 4 digits + HMAC-SHA256 hash.
# Changing this key makes existing hashes unmatchable. Set it once.
# ---------------------------------------------------------------------------
BANK_HASH_KEY = env_required("BANK_HASH_KEY")


# ---------------------------------------------------------------------------
# External services (used from Phase 9)
# ---------------------------------------------------------------------------
FASTAPI_URL = env_str("FASTAPI_URL", "http://127.0.0.1:8001")
ML_SERVICE_API_KEY = env_str("ML_SERVICE_API_KEY")
ML_SERVICE_TIMEOUT = env_int("ML_SERVICE_TIMEOUT", 10)


# ---------------------------------------------------------------------------
# Logging: console + rotating file (backend/logs/app.log)
# Never log passwords, tokens or full bank account numbers.
# ---------------------------------------------------------------------------
LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_LEVEL = env_str("LOG_LEVEL", "INFO")

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "standard": {"format": "%(asctime)s [%(levelname)s] %(name)s: %(message)s"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "standard"},
        "file": {
            "class": "logging.handlers.RotatingFileHandler",
            "filename": LOG_DIR / "app.log",
            "maxBytes": 5 * 1024 * 1024,
            "backupCount": 3,
            "encoding": "utf-8",
            "formatter": "standard",
        },
    },
    "root": {"handlers": ["console", "file"], "level": LOG_LEVEL},
    "loggers": {
        "django": {"handlers": ["console", "file"], "level": "INFO", "propagate": False},
    },
}

# During "manage.py test", keep output readable and keep fake events (failed logins
# made on purpose by tests) out of logs/app.log. assertLogs() still captures records.
if len(sys.argv) > 1 and sys.argv[1] == "test":
    LOGGING["handlers"] = {"null": {"class": "logging.NullHandler"}}
    LOGGING["root"]["handlers"] = ["null"]
    LOGGING["loggers"]["django"]["handlers"] = ["null"]
