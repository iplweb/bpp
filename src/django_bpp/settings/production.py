# -*- encoding: utf-8 -*-

from .base import *

DEBUG = False
DEBUG_TOOLBAR = False
SENDFILE_BACKEND = 'sendfile.backends.nginx'

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

COMPRESS_ENABLED = not DEBUG
COMPRESS_OFFLINE = False

TEMPLATES[0]['OPTIONS']['loaders'] = [
    ('django.template.loaders.cached.Loader', TEMPLATES[0]['OPTIONS']['loaders'])
]

HTML_MINIFY = True

SESSION_ENGINE = "django.contrib.sessions.backends.cache"

CACHES = {
    'default': {
        'BACKEND': 'django.core.cache.backends.memcached.PyLibMCCache',
        'LOCATION': django_getenv("DJANGO_BPP_MEMCACHE_HOST", '127.0.0.1') + ':11211',
    },
}

CACHE_MIDDLEWARE_SECONDS = 3600 * 24

DATABASES['default']['CONN_MAX_AGE'] = None

NOTIFICATIONS_PORT = None

DATA_UPLOAD_MAX_MEMORY_SIZE = 2621440 * 3 # 7.5 MB
DATA_UPLOAD_MAX_NUMBER_FIELDS =	4000
