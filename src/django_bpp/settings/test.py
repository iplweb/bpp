# -*- encoding: utf-8 -*-

# Konfiguracja hosta 'master'

from .base import *

DEBUG = True

SENDFILE_BACKEND = 'sendfile.backends.simple'

SELENIUM_DRIVER = "Firefox"

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
MEDIA_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', 'media')
)
SENDFILE_ROOT = MEDIA_ROOT

CELERY_ALWAYS_EAGER = True
CELERY_EAGER_PROPAGATES_EXCEPTIONS = True

COMPRESS_ENABLED = True
COMPRESS_OFFLINE = True

NOTIFICATIONS_HOST = 'nginx_http_push'
NOTIFICATIONS_PORT = 80
