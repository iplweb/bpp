# -*- encoding: utf-8 -*-

from .base import *

DEBUG = False
TEMPLATE_DEBUG = DEBUG

SENDFILE_BACKEND = 'sendfile.backends.nginx'

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

COMPRESS_OFFLINE = True

TEMPLATE_LOADERS = (
    ('django.template.loaders.cached.Loader', (
        'django.template.loaders.filesystem.Loader',
        'django.template.loaders.app_directories.Loader',
    )),
)

HTML_MINIFY = True
