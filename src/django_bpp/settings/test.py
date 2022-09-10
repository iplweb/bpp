# Konfiguracja hosta 'master'

import os

from .base import *  # NOQA

DEBUG = True

DEBUG_TOOLBAR = False

SENDFILE_BACKEND = "sendfile.backends.simple"

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
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
