# -*- encoding: utf-8 -*-

# Na WINDOWS trzeba:
# - zainstalowac nodejs
# - zainstalowac npm
# - zainstalowac bower,
# - zainstalowac requirements
#
# Nastepnie uruchamiamy:
# - venv\scripts\activate.bat
# - python manage.py bower install
# - python manage.py collectstatic

import os

os.environ['DJANGO_BPP_RAVEN_CONFIG_URL'] = 'http://4355f955f2ae4522ba06752c05eaff0a:5a62fbddd2ac4c0ab3d25b22c352df2a@sentry.iplweb.pl:9000/13'
os.environ['DJANGO_BPP_HOSTNAME'] = 'localhost'

os.environ['DJANGO_BPP_SECRET_KEY'] = '123'

os.environ['DJANGO_BPP_DB_NAME'] = 'django-bpp'
os.environ['DJANGO_BPP_DB_USER'] = 'django-bpp'
os.environ['DJANGO_BPP_DB_PASSWORD'] = 'test'
os.environ['DJANGO_BPP_DB_HOST'] = 'localhost'
os.environ['DJANGO_BPP_DB_PORT'] = '15432'
os.environ['DJANGO_BPP_REDIS_PORT'] = '16379'

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
