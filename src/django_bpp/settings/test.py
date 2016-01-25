# -*- encoding: utf-8 -*-

# Konfiguracja hosta 'master'

from .base import *

DEBUG = True
TEMPLATE_DEBUG = DEBUG

SENDFILE_BACKEND = 'sendfile.backends.simple'

INSTALLED_APPS += ("django_jenkins", )
INSTALLED_APPS += ("django_nose", )

SELENIUM_DRIVER = "Firefox"

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

COMPRESS_OFFLINE = True
