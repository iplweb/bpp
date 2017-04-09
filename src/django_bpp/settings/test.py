# -*- encoding: utf-8 -*-

# Konfiguracja hosta 'master'

from .base import *

DEBUG = True

SENDFILE_BACKEND = 'sendfile.backends.simple'

SELENIUM_DRIVER = "Firefox"

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

COMPRESS_OFFLINE = True
