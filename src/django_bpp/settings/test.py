# Konfiguracja hosta 'master'

import os

from .base import *  # noqa
from .base import DATABASES, MIDDLEWARE, REDIS_HOST, REDIS_PORT  # noqa

# Per-xdist-worker key prefix on the constance Redis cache.
#
# Constance reads through CONSTANCE_DATABASE_CACHE_BACKEND. Under
# `pytest -n auto`, workers have separate Postgres DBs but would otherwise
# share one Redis DB; values cached by worker A would leak into worker B's
# read path. We segregate by KEY_PREFIX (not DB number) so the scheme is
# not bounded by Redis's 16-DB default — `pytest -n auto` on 10+ cores
# would overflow a DB-per-worker scheme.
_CONSTANCE_KEY_PREFIX = os.environ.get("PYTEST_XDIST_WORKER", "master")

DEBUG = True

DEBUG_TOOLBAR = False

SENDFILE_BACKEND = "django_sendfile.backends.simple"

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
MEDIA_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "media")
)
SENDFILE_ROOT = MEDIA_ROOT

CELERY_ALWAYS_EAGER = True
CELERY_EAGER_PROPAGATES_EXCEPTIONS = True

COMPRESS_ENABLED = True
COMPRESS_OFFLINE = False

DATABASES["default"]["CONN_MAX_AGE"] = 0  # noqa

# Vide komentarz w TEMPLATES[0]["OPTIONS"]["loaders"]
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    },
    "constance_cache": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:{REDIS_PORT}/8",
        "KEY_PREFIX": _CONSTANCE_KEY_PREFIX,
        "OPTIONS": {
            "CONNECTION_POOL_CLASS": "redis.BlockingConnectionPool",
            "CONNECTION_POOL_CLASS_KWARGS": {
                "max_connections": 50,
                "timeout": 20,
            },
        },
    },
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]

# Disable setup wizard middleware during tests
MIDDLEWARE = [
    m
    for m in MIDDLEWARE  # noqa
    if m != "first_run_wizard.middleware.FirstRunWizardMiddleware"  # noqa
]
