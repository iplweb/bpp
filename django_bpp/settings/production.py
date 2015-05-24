# -*- encoding: utf-8 -*-

from .base import *

DEBUG = False
TEMPLATE_DEBUG = DEBUG

SENDFILE_BACKEND = 'sendfile.backends.nginx'

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

MEDIA_ROOT = "/home/%s/django_bpp-media" % django_getenv("USER")
SENDFILE_ROOT = MEDIA_ROOT