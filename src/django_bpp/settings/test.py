# Konfiguracja hosta 'master'

import os

from .base import *  # noqa
from .base import DATABASES, MIDDLEWARE, REDIS_HOST, REDIS_PORT  # noqa

DEBUG = True

DEBUG_TOOLBAR = False

SENDFILE_BACKEND = "django_sendfile.backends.simple"

SELENIUM_DRIVER = "Firefox"


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

HTML_MINIFY = False

DATABASES["default"]["CONN_MAX_AGE"] = 0  # noqa

# Vide komentarz w TEMPLATES[0]["OPTIONS"]["loaders"]
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    },
    "constance_cache": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:{REDIS_PORT}/8",  # DB 8 for constance
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
