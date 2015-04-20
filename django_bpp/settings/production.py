# -*- encoding: utf-8 -*-

from .base import *

DEBUG = True
TEMPLATE_DEBUG = DEBUG

SENDFILE_BACKEND = 'sendfile.backends.nginx'

SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = False

MEDIA_ROOT = "/home/%s/django-bpp-media" % django_getenv("USER")
SENDFILE_ROOT = MEDIA_ROOT