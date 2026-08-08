"""
Django settings for the Sansthan Divine Ops backend.
Reads configuration from environment variables (.env) — nothing is hardcoded.
"""

from datetime import timedelta
from pathlib import Path
import os
from dotenv import load_dotenv

from decouple import Csv, config

import os

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
# ---------------------------------------------------------------------------
# Core
# ---------------------------------------------------------------------------
SECRET_KEY = config("SECRET_KEY", default="dev-insecure-secret-key")
DEBUG = config("DEBUG", default=True, cast=bool)
# ALLOWED_HOSTS = config(
#     "ALLOWED_HOSTS",
#     default="localhost,127.0.0.1,192.168.1.39,192.168.1.35",
#     cast=Csv(),
# )

ALLOWED_HOSTS = ['*']


if DEBUG:
    EMAIL_BACKEND = "accounts.email_backend.RelaxedSSLEmailBackend"
else:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"

AUTH_USER_MODEL = "accounts.User"

# ---------------------------------------------------------------------------
# Firebase Admin — used to verify Google sign-in tokens from the Flutter app
# ---------------------------------------------------------------------------
FIREBASE_SERVICE_ACCOUNT_PATH = config(
    "FIREBASE_SERVICE_ACCOUNT_PATH",
    default=str(BASE_DIR / "firebase-service-account.json"),
)

# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "daphne",   # must be first
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "rest_framework_simplejwt",
    "corsheaders",
    "payments",
    "django_filters",
    "channels",
    "accounts",
    "dashboard",
    "django_extensions",
    "devotees",
    "volunteers",
    "bookings",
    "donations",
    "events",
    "inventory",
    "content",
    "reports",
    "communication",
    "tasks",
    "platform_admin",
    "incidents",
    "sos",
    "crowd_status",
]


MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
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
                "django.template.context_processors.debug",
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
# Database — PostgreSQL
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("DB_NAME", default="sansthan_db"),
        "USER": config("DB_USER", default="postgres"),
        "PASSWORD": config("DB_PASSWORD", default="raj18"),
        "HOST": config("DB_HOST", default="localhost"),
        "PORT": config("DB_PORT", default="5432"),
    }
}

# ---------------------------------------------------------------------------
# Password validation
# ---------------------------------------------------------------------------
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator", "OPTIONS": {"min_length": 8}},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# Internationalization
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "Asia/Kolkata"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static files
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# Media files — volunteer photo uploads
# ---------------------------------------------------------------------------
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"


RAZORPAY_KEY_ID = os.environ.get("RAZORPAY_KEY_ID")
RAZORPAY_KEY_SECRET = os.environ.get("RAZORPAY_KEY_SECRET")

if not RAZORPAY_KEY_ID or not RAZORPAY_KEY_SECRET:
    import warnings
    warnings.warn("RAZORPAY_KEY_ID / RAZORPAY_KEY_SECRET not set in environment")

# Multipart upload size (photo capture from camera can be a few MB)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024  # 10 MB
FILE_UPLOAD_MAX_MEMORY_SIZE = 10 * 1024 * 1024

# ---------------------------------------------------------------------------
# Live Ganpati Darshan — config-driven, no database row involved.
# Change this whenever a new live stream starts (and restart the server,
# or set it as an actual OS/host env var so a process manager restart
# picks it up without a code deploy). Leave it empty ("") to hide the
# banner on every dashboard.
# ---------------------------------------------------------------------------
GANPATI_LIVE_URL = config(
    "GANPATI_LIVE_URL",
    default="https://www.youtube.com/live/1oS-N5Y0QHI?si=F9zTnQsmIrsisyQI",
)

# ---------------------------------------------------------------------------
# CORS — allow the Vite frontend to call the API
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = config(
    "CORS_ALLOWED_ORIGINS",
    default="http://localhost:5173,http://127.0.0.1:5173,http://localhost:8080,http://127.0.0.1:8080,http://localhost:3000,http://127.0.0.1:3000",
    cast=Csv(),
)
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# Django REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": (
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ),
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ),
    # Scoped rate limit used by the Volunteer Meal QR check-in/out endpoint.
    # Legitimate use is ~2 scans/day per volunteer (in + out); 10/min per user
    # gives generous headroom for retries/network hiccups while still blocking
    # any abuse pattern (e.g. scripted repeat calls).
    "DEFAULT_THROTTLE_RATES": {
        "meal_scan": "10/min",
    },
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=config("ACCESS_TOKEN_LIFETIME_MIN", default=60, cast=int)),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=config("REFRESH_TOKEN_LIFETIME_DAYS", default=7, cast=int)),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "AUTH_HEADER_TYPES": ("Bearer",),
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
}


import os

# EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = "smtp.gmail.com"          # or your provider
EMAIL_PORT = 587
EMAIL_USE_TLS = True
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD")
DEFAULT_FROM_EMAIL = "Divine Connect <noreply@yourdomain.com>"

# ---------------------------------------------------------------------------
# Channels — WebSocket support for real-time volunteer notifications/status
# ---------------------------------------------------------------------------
REDIS_URL = config("REDIS_URL", default="redis://localhost:6379/0")


# QR encryption key for the devotee/volunteer check-in system (crowd_status app).
# Generate once with:
#   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# then put the value in your .env as QR_ENCRYPTION_KEY=... — never commit the
# actual key. QR_ENCRYPTION_KEY_PREVIOUS is only set temporarily during a key
# rotation so QR codes issued under the old key still decrypt.
QR_ENCRYPTION_KEY = config("QR_ENCRYPTION_KEY", default=None)
QR_ENCRYPTION_KEY_PREVIOUS = config("QR_ENCRYPTION_KEY_PREVIOUS", default=None)

if not QR_ENCRYPTION_KEY:
    if DEBUG:
        # Dev-only fallback so runserver doesn't hard-crash without a .env
        # entry yet. Not persisted — restarting the server invalidates any
        # QR codes issued under it. Never let this branch run when DEBUG=False.
        from cryptography.fernet import Fernet as _Fernet
        QR_ENCRYPTION_KEY = _Fernet.generate_key().decode()
        warnings.warn(
            "QR_ENCRYPTION_KEY not set — using a throwaway dev key that will "
            "change on every restart. Set QR_ENCRYPTION_KEY in your .env before "
            "generating any QR codes you intend to keep working."
        )
    else:
        raise RuntimeError("QR_ENCRYPTION_KEY environment variable is required when DEBUG=False.")

if config("USE_REDIS_CHANNEL_LAYER", default=False, cast=bool):
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels_redis.core.RedisChannelLayer",
            "CONFIG": {"hosts": [REDIS_URL]},
        }
    }
else:
    # Dev-friendly fallback — no Redis required. Switch to the Redis layer
    # above (set USE_REDIS_CHANNEL_LAYER=True in .env) once Redis is running,
    # since InMemoryChannelLayer only works within a single process.
    CHANNEL_LAYERS = {
        "default": {
            "BACKEND": "channels.layers.InMemoryChannelLayer",
        }
    }

# ---------------------------------------------------------------------------
# Celery — background/scheduled tasks (auto-reject volunteer approvals, etc.)
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = config("CELERY_BROKER_URL", default=REDIS_URL)
CELERY_RESULT_BACKEND = config("CELERY_RESULT_BACKEND", default=REDIS_URL)
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = TIME_ZONE

CELERY_BEAT_SCHEDULE = {
    "auto-reject-volunteer-approvals": {
        "task": "volunteers.tasks.auto_reject_expired_approvals",
        "schedule": 300.0,  # every 5 minutes
    },
}