# -*- encoding: utf-8 -*-

import os

def setenv_default(varname, default_value):
    if os.environ.get(varname) is None:
        os.environ[varname] = default_value

setenv_default("DJANGO_SETTINGS_MODULE", "django_bpp.settings.local")
setenv_default("DJANGO_BPP_HOSTNAME", "localhost")
setenv_default("DJANGO_BPP_SECRET_KEY", "123")
setenv_default("DJANGO_BPP_DB_NAME", "test_bpp")
setenv_default("DJANGO_BPP_DB_USER", "test_bpp")
setenv_default("DJANGO_BPP_DB_PASSWORD", "12345678")
setenv_default("DJANGO_BPP_DB_HOST", "192.168.111.100")
setenv_default("DJANGO_BPP_DB_PORT", "5432")
setenv_default("DJANGO_BPP_RAVEN_CONFIG_URL", "http://4355f955f2ae4522ba06752c05eaff0a:5a62fbddd2ac4c0ab3d25b22c352df2a@sentry.iplweb.pl:9000/13")
setenv_default("DJANGO_BPP_REDIS_PORT", "6379")
setenv_default("DJANGO_BPP_REDIS_HOST", "192.168.111.100")


from .base import *

DEBUG = True
TEMPLATE_DEBUG = DEBUG

SENDFILE_BACKEND = 'sendfile.backends.simple'

INSTALLED_APPS += ("django_jenkins", )
INSTALLED_APPS += ("django_nose", )

SELENIUM_DRIVER = "Firefox"

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

MEDIA_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', 'media')
)
SENDFILE_ROOT = MEDIA_ROOT

COMPRESS_OFFLINE = False

COMPRESS_ENABLED = False

# host dla HTMLu oraz linii polecen, reszta dla linii polecen (bo HTML sie autokonfiguruje...)
NOTIFICATIONS_HOST = 'staging-bpp.local'
NOTIFICATIONS_PORT = 80
NOTIFICATIONS_PROTOCOL = 'http'

HTML_MINIFY = False
