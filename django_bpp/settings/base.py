# -*- encoding: utf-8 -*-

import sys, os
from django.core.exceptions import ImproperlyConfigured


def django_getenv(varname, default=None):
    value = os.getenv(varname, default)
    if value is None:
        raise ImproperlyConfigured("Please set %r variable" % varname)
    return value

# pycharm, leave this
os

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))

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
    'password_policies.context_processors.password_status',

    'bpp.context_processors.uczelnia',
    'notifications.context_processors.notification_settings'

)

MIDDLEWARE_CLASSES = (
    'htmlmin.middleware.HtmlMinifyMiddleware',
    'htmlmin.middleware.MarkRequestMiddleware',

    'django.middleware.common.CommonMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'password_policies.middleware.PasswordChangeMiddleware',


    'bpp.middleware.ProfileMiddleware',
    'pagination.middleware.PaginationMiddleware',
    'django_tables2_reports.middleware.TableReportMiddleware',

    'session_security.middleware.SessionSecurityMiddleware',
    'notifications.middleware.NotificationsMiddleware'

)

INTERNAL_IPS = ('127.0.0.1',)

ROOT_URLCONF = 'django_bpp.urls'

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = 'django_bpp.wsgi.application'

TEMPLATE_DIRS = (
    os.path.join(BASE_DIR, 'templates'),
)

INSTALLED_APPS = [
    'django.contrib.humanize',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sessions',
    'django.contrib.sites',
    'password_policies',

    'celery',

    'cookielaw',

    'grappelli',
    'django.contrib.admin',

    'bpp',

    'admin_tools',
    'admin_tools.theming',
    'admin_tools.menu',
    'admin_tools.dashboard',

    'django_tables2',
    'django_tables2_reports',

    'autocomplete_light',

    'messages_extends',

    'pagination',

    'multiseek',
    'django_extensions',
    'celeryui',

    'crispy_forms',
    'crispy_forms_foundation',

    'djangobower',
    'compressor',
    'djorm_pgarray',

    'secure_input',
    'session_security',

    'notifications'
]


# Profile użytkowników
AUTH_USER_MODEL = "bpp.BppUser"

GRAPPELLI_INDEX_DASHBOARD = 'django_bpp.dashboard.CustomIndexDashboard'
GRAPPELLI_ADMIN_TITLE = "BPP"
ADMIN_TOOLS_MENU = 'django_bpp.menu.CustomMenu'

PROJECT_ROOT = BASE_DIR

MULTISEEK_REGISTRY = 'bpp.multiseek_registry'

from bpp.util import slugify_function

AUTOSLUG_SLUGIFY_FUNCTION = slugify_function

LOGIN_REDIRECT_URL = '/'

# django
MEDIA_URL = '/media/'

INTERNAL_IPS = ('127.0.0.1',)

# djorm-pool
DJORM_POOL_OPTIONS = {
    "pool_size": 30,
    "max_overflow": 0,
    "recycle": 3600, # the default value
}

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
        'celery.worker.job': {
            'level': 'ERROR',
            'handlers': ['sentry'],
            'propagate': False
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
        '..', '..', 'components'))

BOWER_INSTALLED_APPS = (
    'jquery#2.1.1',
    'jeditable#1.7.3',
    'jqueryui#1.11.0',
    'foundation#5.5.2',
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

SITE_ROOT = os.path.abspath(
    os.path.join(
        os.path.dirname(__file__), '..', '..'))

STATIC_ROOT = os.path.join(SITE_ROOT, "staticroot")

COMPRESS_ENABLED = True
COMPRESS_ROOT = STATIC_ROOT

# Domyslnie, redis na Ubuntu pozwala na 16 baz danych
REDIS_DB_BROKER = 1
REDIS_DB_CELERY = 2
REDIS_DB_SESSION = 4
REDIS_DB_CACHEOPS = 5
REDIS_DB_LOCKS = 6

if os.getenv("DJANGO_BPP_RAVEN_CONFIG_URL", None):
    RAVEN_CONFIG = {
        'dsn': django_getenv("DJANGO_BPP_RAVEN_CONFIG_URL"),
    }

    INSTALLED_APPS.append('raven.contrib.django.raven_compat')

ALLOWED_HOSTS = [
    django_getenv("DJANGO_BPP_HOSTNAME"),
]

REDIS_HOST = django_getenv("DJANGO_BPP_REDIS_HOST", "localhost")
REDIS_PORT = int(django_getenv("DJANGO_BPP_REDIS_PORT", "6379"))

CACHEOPS_REDIS = {
    'host': REDIS_HOST, # redis-server is on same machine
    'port': REDIS_PORT,        # default redis port
    'db': REDIS_DB_CACHEOPS, # "redis://%s:%s/%s" % (REDIS_HOST, REDIS_PORT, REDIS_DB_CACHEOPS),
    'socket_timeout': 3,
}

BROKER_URL = django_getenv("DJANGO_BPP_BROKER_URL", "amqp://guest:guest@localhost:5672//")
# BYłO: redis://%s:%s/%s' % (REDIS_HOST, REDIS_PORT, REDIS_DB_BROKER)
# CELERY_RESULT_BACKEND = 'redis://%s:%s/%s' % (REDIS_HOST, REDIS_PORT, REDIS_DB_CELERY)

#
SESSION_REDIS_HOST = REDIS_HOST
SESSION_REDIS_PORT = REDIS_PORT
SESSION_REDIS_DB = REDIS_DB_SESSION
SESSION_REDIS_PREFIX = 'session'

ALLOWED_TAGS = ('b', 'em', 'i', 'strong', 'strike', 'u', 'sup', 'font', 'sub')

SESSION_SECURITY_PASSIVE_URLS = [
    '/messages/'
]

ADMINS = (
    ("Michal Pasternak", "michal.dtz@gmail.com"),
)
MANAGERS = ADMINS

def int_or_None(value):
    try:
        return int(value)
    except ValueError:
        return ""

DATABASES = {
    'default': {
        'ENGINE': django_getenv("DJANGO_BPP_DB_ENGINE", 'django.db.backends.postgresql_psycopg2'),
        'NAME': django_getenv("DJANGO_BPP_DB_NAME"),
        'USER': django_getenv("DJANGO_BPP_DB_USER"),
        'PASSWORD': django_getenv("DJANGO_BPP_DB_PASSWORD"),
        'HOST': django_getenv("DJANGO_BPP_DB_HOST", ""),
        'PORT': int_or_None(django_getenv("DJANGO_BPP_DB_PORT", "")),
    }
}

SECRET_KEY = django_getenv("DJANGO_BPP_SECRET_KEY")

SENDFILE_URL = MEDIA_URL

# django-password-policies
# Zmiana hasla co 30 dni
PASSWORD_DURATION_SECONDS = (60 * 60 * 24) * 30
PASSWORD_USE_HISTORY = True
PASSWORD_HISTORY_COUNT = 12
# wymagane przez django-password-policies
SESSION_SERIALIZER='django.contrib.sessions.serializers.PickleSerializer'


MESSAGE_STORAGE = 'messages_extends.storages.FallbackStorage'

NOTIFICATIONS_PUB_PREFIX = 'django_bpp'

TEST_NON_SERIALIZED_APPS = ['django.contrib.contenttypes',
                            'django.contrib.auth']

TESTING = ('test' in sys.argv) or ('jenkins' in sys.argv) or ('py.test' in sys.argv)
if TESTING:
    CELERY_ALWAYS_EAGER = True

CELERYD_HIJACK_ROOT_LOGGER = False
