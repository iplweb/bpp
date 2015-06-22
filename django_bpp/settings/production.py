# -*- encoding: utf-8 -*-

from .base import *

DEBUG = False
TEMPLATE_DEBUG = DEBUG

SENDFILE_BACKEND = 'sendfile.backends.nginx'

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

MEDIA_ROOT = "/home/%s/django_bpp-media" % django_getenv("USER")
SENDFILE_ROOT = MEDIA_ROOT

COMPRESS_OFFLINE = True

# host dla HTMLu oraz linii polecen, reszta dla linii polecen (bo HTML sie autokonfiguruje...)
NOTIFICATIONS_HOST = 'bpp.umlub.pl'
NOTIFICATIONS_PORT = None
NOTIFICATIONS_PROTOCOL = 'http'


TEMPLATE_LOADERS = (
    ('django.template.loaders.cached.Loader', (
        'django.template.loaders.filesystem.Loader',
        'django.template.loaders.app_directories.Loader',
    )),
)

HTML_MINIFY = True

# DATABASES['default']['CONN_MAX_AGE'] = 600

