"""
Minimal Django settings for lightweight auth server.

Only loads apps required for session-based authentication.
Imports shared settings from base.py to ensure consistency with the main app
(same SECRET_KEY, database, session backend).

This auth server is designed to:
- Start quickly (seconds, not minutes)
- Validate Django sessions for nginx auth_request
- Share sessions with the main BPP application
"""

from pathlib import Path

# Import shared configuration from base settings
# These imports define Django settings - they ARE used by Django's settings machinery
# even though they appear "unused" to static analysis tools
from django_bpp.settings.production import (  # noqa: F401
    # User model
    AUTH_USER_MODEL,
    # CSRF trusted origins for login form
    CSRF_TRUSTED_ORIGINS,
    DATABASES,
    DEFAULT_AUTO_FIELD,
    # Redis settings
    REDIS_HOST,
    REDIS_PORT,
    # Rollbar configuration
    ROLLBAR,
    # Critical shared settings (Django reads these from module namespace)
    SECRET_KEY,
    SESSION_COOKIE_HTTPONLY,
    SESSION_COOKIE_SECURE,
    SESSION_EXPIRE_AT_BROWSER_CLOSE,
    # Session settings
    SESSION_SERIALIZER,
    TIME_ZONE,
    # Timezone
    USE_TZ,
    # env function for reading environment variables
    env,
)

DEBUG = False
ALLOWED_HOSTS = ["*"]

# Minimal apps - only what's needed for auth
INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "bpp",  # Required for AUTH_USER_MODEL = "bpp.BppUser"
]

# Minimal middleware (includes CSRF for login form)
MIDDLEWARE = [
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
]

ROOT_URLCONF = "django_bpp.urls_auth_server"

# Minimal template configuration for login form
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            Path(__file__).resolve().parent.parent / "templates",
        ],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
            ],
        },
    },
]

# Use cache-based sessions (same as production.py)
# This uses Redis cache for session storage
SESSION_ENGINE = "django.contrib.sessions.backends.cache"

# Cache configuration for sessions
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:{REDIS_PORT}",
        "OPTIONS": {
            "DB": env("DJANGO_BPP_REDIS_DB_CACHE"),
            "CONNECTION_POOL_CLASS": "redis.BlockingConnectionPool",
            "CONNECTION_POOL_CLASS_KWARGS": {
                "max_connections": 10,
                "timeout": 10,
            },
        },
    },
}

# Login URLs for the emergency login form
LOGIN_URL = "/__external_auth/login/"
LOGIN_REDIRECT_URL = "/"

# Logging - minimal but useful for debugging
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
}
