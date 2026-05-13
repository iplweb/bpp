# Konfiguracja hosta 'master'

import os
import re

from .base import *  # noqa
from .base import DATABASES, MIDDLEWARE, REDIS_HOST, REDIS_PORT  # noqa

# Per-xdist-worker Redis DB for the constance cache.
#
# Constance reads through a Django cache backend (CONSTANCE_DATABASE_CACHE_BACKEND).
# Under `pytest -n auto`, every xdist worker gets its own Postgres DB but they
# would otherwise share one Redis DB — so a value cached by worker A leaks into
# worker B and `isinstance(value, bool)` style assertions go flaky (bool is an
# int subclass, the reverse is not true).
#
# redis:7-alpine ships with 16 DBs (0..15). Tests use DBs 1, 2, 4, 6, 7 for
# broker/celery/session/locks/cacheops. We reserve DBs 8..15 for constance
# (one per worker), so up to 8 parallel workers are supported. Master process
# and non-xdist runs get DB 8.
_xdist_worker = os.environ.get("PYTEST_XDIST_WORKER", "")
_match = re.match(r"^gw(\d+)$", _xdist_worker)
_constance_worker_idx = int(_match.group(1)) if _match else 0
assert _constance_worker_idx < 8, (
    f"pytest-xdist worker index {_constance_worker_idx} exceeds the 8-DB "
    f"allotment for the constance cache (Redis DBs 8..15). Run with -n <= 8, "
    f"or extend the testcontainer Redis with --databases N and widen this range."
)
_CONSTANCE_REDIS_DB = 8 + _constance_worker_idx

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
        "LOCATION": f"redis://{REDIS_HOST}:{REDIS_PORT}/{_CONSTANCE_REDIS_DB}",
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
    if m != "bpp_setup_wizard.middleware.SetupWizardMiddleware"  # noqa
]
