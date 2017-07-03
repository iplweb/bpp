# -*- encoding: utf-8 -*-

from .base import *

DEBUG = False

SENDFILE_BACKEND = 'sendfile.backends.nginx'

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

COMPRESS_ENABLED = not DEBUG
COMPRESS_OFFLINE = False

TEMPLATES[0]['OPTIONS']['loaders'] = [
    ('django.template.loaders.cached.Loader', TEMPLATES[0]['OPTIONS']['loaders'])
]

HTML_MINIFY = True
