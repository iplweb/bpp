# -*- encoding: utf-8 -*-

import os, sys

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))

# Django
import random, string

TIME_ZONE = 'Europe/Warsaw'
LANGUAGE_CODE = 'pl'
SITE_ID = 1
USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = '/static/'

ADMIN_MEDIA_PREFIX = '/static/admin/'
STATICFILES_DIRS = (
# Put strings here, like "/home/html/static" or "C:/www/django/static".
# Always use forward slashes, even on Windows.
# Don't forget to use absolute paths, not relative paths.
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    'django.contrib.staticfiles.finders.AppDirectoriesFinder',
    'django.contrib.staticfiles.finders.FileSystemFinder',
    'djangobower.finders.BowerFinder',
    'compressor.finders.CompressorFinder'
    #    'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = '=6uqi1)(qnzjo8q@-@m#egd8v#+zac6feh2h-b&amp;=3bczpfqxxd'

# List of callables that know how to import templates from various sources.
TEMPLATE_LOADERS = (
    'django.template.loaders.filesystem.Loader',
    'django.template.loaders.app_directories.Loader',
    #     'django.template.loaders.eggs.Loader',
)

TEMPLATE_CONTEXT_PROCESSORS = (
    'django.contrib.auth.context_processors.auth',
    'django.core.context_processors.debug',
    'django.core.context_processors.i18n',
    'django.core.context_processors.media',
    'django.core.context_processors.request',
    'django.core.context_processors.static',
    'django.contrib.messages.context_processors.messages',
    'bpp.context_processors.uczelnia'

)

MIDDLEWARE_CLASSES = (
    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',

    'bpp.middleware.ProfileMiddleware',
    'pagination.middleware.PaginationMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django_tables2_reports.middleware.TableReportMiddleware',
)

INTERNAL_IPS = ('127.0.0.1',)

ROOT_URLCONF = 'django_bpp.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'django_bpp.wsgi.application'

TEMPLATE_DIRS = (
    os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'templates')),
)

INSTALLED_APPS = [
    'django.contrib.humanize',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sessions',
    'celery',

    'cookielaw',

    'grappelli',
    'django.contrib.admin',

    'bpp',

    'admin_tools',
    'admin_tools.theming',
    'admin_tools.menu',
    'admin_tools.dashboard',

    'django_extensions',

    'django_tables2',
    'django_tables2_reports',

    'autocomplete_light',

    'django_sse',
    'corsheaders',
    'monitio',

    'pagination',

    'multiseek',
    'celeryui',

    'crispy_forms',
    'crispy_forms_foundation',

    'djangobower',
    'compressor',
    'djorm_pgarray',

    'secure_input',

]


# Profile użytkowników
AUTH_USER_MODEL = "bpp.BppUser"

GRAPPELLI_INDEX_DASHBOARD = 'django_bpp.dashboard.CustomIndexDashboard'
GRAPPELLI_ADMIN_TITLE = "BPP"
ADMIN_TOOLS_MENU = 'django_bpp.menu.CustomMenu'

PROJECT_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(os.path.realpath(__file__)),
        '', '..'))

MULTISEEK_REGISTRY = 'bpp.multiseek_registry'

from bpp.util import slugify_function

AUTOSLUG_SLUGIFY_FUNCTION = slugify_function

LOGIN_REDIRECT_URL = '/'

# django-monitio
MESSAGE_STORAGE = 'monitio.storage.PersistentMessageStorage'
MONITIO_EXCLUDE_READ = True

# django-cors
CORS_ORIGIN_WHITELIST = ()

# django
MEDIA_URL = '/media/'

INTERNAL_IPS = ('127.0.0.1',)

# djorm-pool
DJORM_POOL_OPTIONS = {
    "pool_size": 30,
    "max_overflow": 0,
    "recycle": 3600, # the default value
}

TESTING = ('test' in sys.argv) or ('jenkins' in sys.argv)


DJANGO_BPP_DATABASE_NAME = os.getenv('DJANGO_BPP_DATABASE_NAME', 'django_bpp')

# django-jenkins

JENKINS_TASKS = []
#    'django_jenkins.tasks.run_pylint',
#    'django_jenkins.tasks.run_pep8',
#    'django_jenkins.tasks.run_pyflakes',
#    'django_jenkins.tasks.run_flake8',
#    'django_jenkins.tasks.with_coverage',


LOGGING = {
    'version': 1,
    'disable_existing_loggers': True,
    'root': {
        'level': 'WARNING',
        'handlers': ['sentry'],
    },
    'formatters': {
        'verbose': {
            'format': '%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s'
        },
    },
    'handlers': {
        'sentry': {
            'level': 'ERROR',
            'class': 'raven.contrib.django.raven_compat.handlers.SentryHandler',
        },
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose'
        }
    },
    'loggers': {
        'django.db.backends': {
            'level': 'ERROR',
            'handlers': ['console'],
            'propagate': False,
        },
        'raven': {
            'level': 'DEBUG',
            'handlers': ['console'],
            'propagate': False,
        },
        'sentry.errors': {
            'level': 'DEBUG',
            'handlers': ['console'],
            'propagate': False,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}

EXCEL_SUPPORT = 'openpyxl'

TOPLEVEL = 'common'

TEST_RUNNER = 'django.test.runner.DiscoverRunner'

PROJECT_APPS = (
    'bpp',
)


# Ustawienia ModelMommy

def autoslug_gen():
    return ''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(50))


MOMMY_CUSTOM_FIELDS_GEN = {
    'autoslug.fields.AutoSlugField': autoslug_gen
}


# Ustawienia Bower

BOWER_COMPONENTS_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__),
        '', '..', 'components'))

BOWER_INSTALLED_APPS = (
    'jquery#2.1.1',
    'jeditable#1.7.3',
    'jqueryui#1.11.0',
    'foundation#5.4.6',
    'foundation-datepicker',
    'font-awesome#4.1.0',
    'iframe-resizer#2.5.1',
    'jinplace#1.0.1',
    'http://keith-wood.name/zip/jquery.keypad.package-2.0.1.zip'
)

CRISPY_TEMPLATE_PACK = 'foundation-5'

SESSION_ENGINE = 'redis_sessions.session'

SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTOCOL', 'https')





CACHEOPS = {
    # Automatically cache any User.objects.get() calls for 15 minutes
    # This includes request.user or post.author access,
    # where Post.author is a foreign key to auth.User
    'auth.user': ('get', 60*15),
    'bpp.bppuser': ('get', 60*15),

    'contenttypes.*': ('get', 60*60),

    'bpp.uczelnia': ('all', 60*60*3),
    'bpp.jednostka': ('all', 60*15),
    'bpp.wydzial': ('all', 60*15),
    'bpp.autor': ('get', 60*15),

    'bpp.zrodlo': ('all', 60*15),

    'multiseek.searchform': ('all', 60*15),

    'bpp.charakter_formalny': ('all', 60*15),
    'bpp.typ_kbn': ('all', 60*15),
    'bpp.jezyk': ('all', 60*15),
    'bpp.typ_odpowiedzialnosci': ('all', 60*15),
    'bpp.status_korekty': ('all', 60*15),


    # Automatically cache all gets, queryset fetches and counts
    # to other django.contrib.auth models for an hour
    'auth.*': ('all', 60*60),

    # Enable manual caching on all news models with default timeout of an hour
    # Use News.objects.cache().get(...)
    #  or Tags.objects.filter(...).order_by(...).cache()
    # to cache particular ORM request.
    # Invalidation is still automatic
    #'news.*': ('just_enable', 60*60),

    # Automatically cache count requests for all other models for 15 min
    #'*.*': ('count', 60*15),
}

CACHEOPS_DEGRADE_ON_FAILURE = True

MAT_VIEW_REFRESH_COUNTDOWN = 30

from .local_settings import *

SITE_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__), '..'))

STATIC_ROOT = os.path.join(SITE_ROOT, "staticroot")
MEDIA_ROOT = os.path.join(SITE_ROOT, "mediaroot")

COMPRESS_ENABLED = True
COMPRESS_ROOT = STATIC_ROOT

INSTALLED_APPS.extend(EXTRA_INSTALLED_APPS)

CACHEOPS_REDIS = {
    'host': REDIS_HOST, # redis-server is on same machine
    'port': REDIS_PORT,        # default redis port
    'db': REDIS_DB_CACHEOPS, # "redis://%s:%s/%s" % (REDIS_HOST, REDIS_PORT, REDIS_DB_CACHEOPS), 
    'socket_timeout': 3,
}

BROKER_URL = 'redis://%s:%s/%s' % (REDIS_HOST, REDIS_PORT, REDIS_DB_BROKER)
CELERY_RESULT_BACKEND = 'redis://%s:%s/%s' % (REDIS_HOST, REDIS_PORT, REDIS_DB_CELERY)

# django-monitio
REDIS_SSEQUEUE_CONNECTION_SETTINGS = {
    'location': '%s:%s' % (REDIS_HOST, REDIS_PORT),
    'db': REDIS_DB_MONITIO,
}

#
SESSION_REDIS_HOST = REDIS_HOST
SESSION_REDIS_PORT = REDIS_PORT
SESSION_REDIS_DB = REDIS_DB_SESSION
SESSION_REDIS_PREFIX = 'session'

# django-sendfile
SENDFILE_ROOT = MEDIA_ROOT
SENDFILE_URL = MEDIA_URL

if TESTING:
    CELERY_ALWAYS_EAGER = True

COMPRESS_OFFLINE = True
COMPRESS_ENABLED = False

ALLOWED_TAGS = ('b', 'em', 'i', 'strong', 'strike', 'u', 'sup', 'font', 'sub')

