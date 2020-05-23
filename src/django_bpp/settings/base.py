# -*- encoding: utf-8 -*-

import os
import random
import string
import sys
from datetime import timedelta

import sentry_sdk
from django.core.exceptions import DisallowedHost, ImproperlyConfigured
from sentry_sdk.integrations.django import DjangoIntegration

from bpp.util import slugify_function
from django_bpp.version import VERSION


def django_getenv(varname, default=None):
    value = os.getenv(varname, default)
    if value is None:
        raise ImproperlyConfigured("Please set %r variable" % varname)
    return value


BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))


TIME_ZONE = "Europe/Warsaw"
LANGUAGE_CODE = "pl"
LANGUAGES = (("pl", "Polish"),)

SITE_ID = 1  # dla static-sitemaps
USE_I18N = True
USE_L10N = True
USE_TZ = True

STATIC_URL = "/static/"

ADMIN_MEDIA_PREFIX = "/static/admin/"
STATICFILES_DIRS = (
    # Put strings here, like "/home/html/static" or "C:/www/django/static".
    # Always use forward slashes, even on Windows.
    # Don't forget to use absolute paths, not relative paths.
)

# List of finder classes that know how to find static files in
# various locations.
STATICFILES_FINDERS = (
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "bpp.finders.YarnFinder",
    "compressor.finders.CompressorFinder",
    #    'django.contrib.staticfiles.finders.DefaultStorageFinder',
)

# Make this unique, and don't share it with anybody.
SECRET_KEY = "=6uqi1)(qnzjo8q@-@m#egd8v#+zac6feh2h-b&amp;=3bczpfqxxd"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates"),],
        "OPTIONS": {
            "loaders": [
                "admin_tools.template_loaders.Loader",
                "django.template.loaders.filesystem.Loader",
                "django.template.loaders.app_directories.Loader",
            ],
            "context_processors": [
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.debug",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.request",
                "django.template.context_processors.static",
                "django.contrib.messages.context_processors.messages",
                "password_policies.context_processors.password_status",
                "bpp.context_processors.uczelnia.uczelnia",
                "bpp.context_processors.config.theme_name",
                "bpp.context_processors.config.enable_new_reports",
                "bpp.context_processors.global_nav.user",
                "bpp.context_processors.google_analytics.google_analytics",
                "notifications.context_processors.notification_settings",
            ],
        },
    },
]

MIDDLEWARE = [
    "htmlmin.middleware.HtmlMinifyMiddleware",
    "htmlmin.middleware.MarkRequestMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    # "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "password_policies.middleware.PasswordChangeMiddleware",
    "dj_pagination.middleware.PaginationMiddleware",
    "session_security.middleware.SessionSecurityMiddleware",
    "notifications.middleware.NotificationsMiddleware",
]

INTERNAL_IPS = ("127.0.0.1",)

ROOT_URLCONF = "django_bpp.urls"

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = "django_bpp.wsgi.application"

INSTALLED_APPS = [
    "django.contrib.humanize",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.sitemaps",
    "django.contrib.postgres",
    "password_policies",
    "create_test_db",
    "celery",
    "flexible_reports",
    "static_sitemaps",
    "cookielaw",
    "columns",
    # Musi być PRZED django-autocomplete-light do momentu
    # dal 3.3.0-release, musi być naprawiony o ten błąd:
    # https://github.com/yourlabs/django-autocomplete-light/issues/981
    "bpp",
    "dal",
    "dal_select2",
    "grappelli",
    "django.contrib.admin",
    "dj_pagination",
    "admin_tools",
    "admin_tools.theming",
    "admin_tools.menu",
    "admin_tools.dashboard",
    "django_tables2",
    # 'FOR_REMOVAL_autocomplete_light',
    "messages_extends",
    "multiseek",
    "django_extensions",
    "celeryui",
    "crispy_forms",
    "crispy_forms_foundation",
    "compressor",
    "session_security",
    "notifications",
    "integrator2",
    "eksport_pbn",
    "nowe_raporty",
    "rozbieznosci_dyscyplin",
    "loginas",
    "robots",
    "webmaster_verification",
    "favicon",
    "miniblog",
    "import_dyscyplin",
    "mptt",
    "raport_slotow",
    "import_dbf",
    "rest_framework",
    "django_filters",
    "api_v1",
    "adminsortable2",
]

# Profile użytkowników
AUTH_USER_MODEL = "bpp.BppUser"

GRAPPELLI_INDEX_DASHBOARD = "django_bpp.dashboard.CustomIndexDashboard"
GRAPPELLI_ADMIN_TITLE = "BPP"
ADMIN_TOOLS_MENU = "django_bpp.menu.CustomMenu"

PROJECT_ROOT = BASE_DIR

MULTISEEK_REGISTRY = "bpp.multiseek_registry"


AUTOSLUG_SLUGIFY_FUNCTION = slugify_function

LOGIN_REDIRECT_URL = "/"

LOGOUT_REDIRECT_URL = LOGIN_REDIRECT_URL

# django
MEDIA_URL = "/media/"

INTERNAL_IPS = ("127.0.0.1",)

# djorm-pool
DJORM_POOL_OPTIONS = {
    "pool_size": 30,
    "max_overflow": 0,
    "recycle": 3600,  # the default value
}


TEST_RUNNER = "django.test.runner.DiscoverRunner"

PROJECT_APPS = ("bpp",)


# Ustawienia ModelMommy


def autoslug_gen():
    return "".join(
        random.choice(string.ascii_uppercase + string.digits) for _ in range(50)
    )


MOMMY_CUSTOM_FIELDS_GEN = {"autoslug.fields.AutoSlugField": autoslug_gen}

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTOCOL", "https")

MAT_VIEW_REFRESH_COUNTDOWN = 30

SCRIPT_PATH = os.path.abspath(os.path.dirname(__file__))

SITE_ROOT = os.path.abspath(os.path.join(SCRIPT_PATH, "..", ".."))

STATIC_ROOT = os.path.join(SCRIPT_PATH, "..", "staticroot")

COMPRESS_CSS_FILTERS = [
    "compressor.filters.css_default.CssAbsoluteFilter",
    "compressor.filters.cssmin.CSSMinFilter",
]
COMPRESS_JS_FILTERS = ["compressor.filters.jsmin.rJSMinFilter"]

COMPRESS_ROOT = STATIC_ROOT
COMPRESS_OFFLINE_CONTEXT = [
    {
        "THEME_NAME": "scss/app-blue.css",
        "STATIC_URL": STATIC_URL,
        "LANGUAGE_CODE": "pl",
    },
    {
        "THEME_NAME": "scss/app-green.css",
        "STATIC_URL": STATIC_URL,
        "LANGUAGE_CODE": "pl",
    },
    {
        "THEME_NAME": "scss/app-orange.css",
        "STATIC_URL": STATIC_URL,
        "LANGUAGE_CODE": "pl",
    },
]

# Domyslnie, redis na Ubuntu pozwala na 16 baz danych
REDIS_DB_BROKER = 1
REDIS_DB_CELERY = 2
REDIS_DB_SESSION = 4
REDIS_DB_LOCKS = 6

SENTRYSDK_CONFIG_URL = os.getenv("DJANGO_BPP_RAVEN_CONFIG_URL", None) or os.getenv(
    "DJANGO_BPP_SENTRYSDK_CONFIG_URL", None
)

if SENTRYSDK_CONFIG_URL:
    sentry_sdk.init(
        dsn=SENTRYSDK_CONFIG_URL,
        integrations=[DjangoIntegration()],
        release=VERSION,
        ignore_errors=[DisallowedHost],
        send_default_pii=True,
    )

ALLOWED_HOSTS = [
    "127.0.0.1",
    django_getenv("DJANGO_BPP_HOSTNAME", "localhost"),
]

REDIS_HOST = django_getenv("DJANGO_BPP_REDIS_HOST", "localhost")
REDIS_PORT = int(django_getenv("DJANGO_BPP_REDIS_PORT", "6379"))

CELERY_HOST = django_getenv("DJANGO_BPP_CELERY_HOST", "localhost")
CELERY_PORT = int(django_getenv("DJANGO_BPP_CELERY_PORT", "5672"))
CELERY_USER = django_getenv("DJANGO_BPP_CELERY_USER", "guest")
CELERY_PASSWORD = django_getenv("DJANGO_BPP_CELERY_PASSWORD", "guest")
CELERY_VHOST = django_getenv("DJANGO_BPP_CELERY_VHOST", "/")

BROKER_URL = django_getenv(
    "DJANGO_BPP_BROKER_URL",
    "amqp://%s:%s@%s:%s/%s"
    % (CELERY_USER, CELERY_PASSWORD, CELERY_HOST, CELERY_PORT, CELERY_VHOST),
)

# CELERY_RESULT_BACKEND = 'redis://%s:%s/%s' % (REDIS_HOST, REDIS_PORT, REDIS_DB_CELERY)
CELERY_RESULT_BACKEND = "rpc://"

#
SESSION_REDIS_HOST = REDIS_HOST
SESSION_REDIS_PORT = REDIS_PORT
SESSION_REDIS_DB = REDIS_DB_SESSION
SESSION_REDIS_PREFIX = "session"

ALLOWED_TAGS = ("b", "em", "i", "strong", "strike", "u", "sup", "font", "sub")

SESSION_SECURITY_PASSIVE_URLS = ["/messages/"]

ADMINS = (("Michal Pasternak", "michal.dtz@gmail.com"),)
MANAGERS = ADMINS


def int_or_None(value):
    try:
        return int(value)
    except ValueError:
        return ""


DATABASES = {
    "default": {
        "ENGINE": django_getenv(
            "DJANGO_BPP_DB_ENGINE", "django.db.backends.postgresql_psycopg2"
        ),
        "NAME": django_getenv("DJANGO_BPP_DB_NAME", "bpp"),
        "USER": django_getenv("DJANGO_BPP_DB_USER", "postgres"),
        "PASSWORD": django_getenv("DJANGO_BPP_DB_PASSWORD", "password"),
        "HOST": django_getenv("DJANGO_BPP_DB_HOST", "localhost"),
        "PORT": int_or_None(django_getenv("DJANGO_BPP_DB_PORT", "5432")),
    },
    # 'test': {
    #     'ENGINE': django_getenv("DJANGO_BPP_DB_ENGINE", 'django.db.backends.postgresql_psycopg2'),
    #     'NAME': django_getenv("DJANGO_BPP_DB_NAME", "test_django-bpp"),
    #     'USER': django_getenv("DJANGO_BPP_DB_USER", "postgres"),
    #     'PASSWORD': django_getenv("DJANGO_BPP_DB_PASSWORD", "password"),
    #     'HOST': django_getenv("DJANGO_BPP_DB_HOST", "localhost"),
    #     'PORT': int_or_None(django_getenv("DJANGO_BPP_DB_PORT", "5432")),
    # },
}

SECRET_KEY = django_getenv("DJANGO_BPP_SECRET_KEY")

SENDFILE_URL = MEDIA_URL

# django-password-policies

# Zmiana hasla co 30 dni
PASSWORD_DURATION_SECONDS = int(
    os.getenv("DJANGO_BPP_PASSWORD_DURATION_SECONDS", str((60 * 60 * 24) * 30))
)

PASSWORD_USE_HISTORY = bool(int(os.getenv("DJANGO_BPP_USE_PASSWORD_HISTORY", "1")))

PASSWORD_HISTORY_COUNT = int(os.getenv("DJANGO_BPP_PASSWORD_HISTORY_COUNT", "12"))

# wymagane przez django-password-policies
SESSION_SERIALIZER = "django.contrib.sessions.serializers.PickleSerializer"

MESSAGE_STORAGE = "messages_extends.storages.FallbackStorage"

NOTIFICATIONS_PUB_PREFIX = "django_bpp"

TEST_NON_SERIALIZED_APPS = ["django.contrib.contenttypes", "django.contrib.auth"]

TESTING = (
    ("test" in sys.argv)
    or ("jenkins" in sys.argv)
    or ("py.test" in sys.argv)
    or ("pytest" in sys.argv)
)

if TESTING:
    CELERY_ALWAYS_EAGER = True
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_EAGER_PROPAGATES_EXCEPTIONS = True

CELERYD_HIJACK_ROOT_LOGGER = False

CELERY_TRACK_STARTED = True

CELERYBEAT_SCHEDULE = {
    "cleanup-integrator2-files": {
        "task": "integrator2.tasks.remove_old_integrator_files",
        "schedule": timedelta(days=1),
    },
    "cleanup-eksport_pbn-files": {
        "task": "eksport_pbn.tasks.remove_old_eksport_pbn_files",
        "schedule": timedelta(days=1),
    },
    "cleanup-report-files": {
        "task": "bpp.tasks.remove_old_report_files",
        "schedule": timedelta(days=1),
    },
    "zaktualizuj-liczbe-cytowan": {
        "task": "bpp.tasks.zaktualizuj_liczbe_cytowan",
        "schedule": timedelta(days=5),
    },
}


def can_login_as(request, target_user):
    return request.user.is_superuser


CAN_LOGIN_AS = can_login_as

#

# host dla HTMLu oraz linii polecen, reszta dla linii polecen (bo HTML sie autokonfiguruje...)
NOTIFICATIONS_HOST = django_getenv("DJANGO_BPP_NOTIFICATIONS_HOST", "127.0.0.1")
NOTIFICATIONS_PORT = django_getenv("DJANGO_BPP_NOTIFICATIONS_PORT", 80)
NOTIFICATIONS_PROTOCOL = django_getenv("DJANGO_BPP_NOTIFICATIONS_PROTOCOL", "http")

MEDIA_ROOT = django_getenv("DJANGO_BPP_MEDIA_ROOT", os.getenv("HOME", "C:/bpp-media"))

SENDFILE_ROOT = MEDIA_ROOT

GOOGLE_ANALYTICS_PROPERTY_ID = django_getenv(
    "DJANGO_BPP_GOOGLE_ANALYTICS_PROPERTY_ID", ""
)

ROBOTS_SITEMAP_VIEW_NAME = "sitemap"

WEBMASTER_VERIFICATION = {
    "google": django_getenv("DJANGO_BPP_GOOGLE_VERIFICATION_CODE", "1111111111111111"),
}

EXCLUDE_FROM_MINIFYING = ["^google.*html$"]

SESSION_EXPIRE_AT_BROWSER_CLOSE = True

UZYWAJ_PUNKTACJI_WEWNETRZNEJ = bool(
    int(django_getenv("DJANGO_BPP_UZYWAJ_PUNKTACJI_WEWNETRZNEJ", "1"))
)

THEME_NAME = os.getenv("DJANGO_BPP_THEME_NAME", "app-blue")

ENABLE_NEW_REPORTS = int(os.getenv("DJANGO_BPP_ENABLE_NEW_REPORTS", "1"))

SESSION_SECURITY_WARN_AFTER = int(
    os.getenv("DJANGO_BPP_SESSION_SECURITY_WARN_AFTER", "540")
)

SESSION_SECURITY_EXPIRE_AFTER = int(
    os.getenv("DJANGO_BPP_SESSION_SECURITY_EXPIRE_AFTER", "600")
)

PUNKTUJ_MONOGRAFIE = bool(int(os.getenv("DJANGO_BPP_PUNKTUJ_MONOGRAFIE", "1")))

STATICSITEMAPS_ROOT_SITEMAP = "django_bpp.sitemaps.django_bpp_sitemaps"
STATICSITEMAPS_REFRESH_AFTER = 24 * 60

# dla django-model-utils SplitField
SPLIT_MARKER = "<!-- tutaj -->"

# django-crispy-forms: użyj crispy-forms-foundation

CRISPY_ALLOWED_TEMPLATE_PACKS = "foundation-6"

CRISPY_TEMPLATE_PACK = "foundation-6"

CRISPY_CLASS_CONVERTERS = {
    "inputelement": None,
    "errorcondition": "is-invalid-input",
}

SILENCED_SYSTEM_CHECKS = ["urls.W003"]

# Sposób generowania inline dla powiązań rekordu autora z rekordem
# publikacji

INLINE_DLA_AUTOROW = os.getenv("DJANGO_BPP_INLINE_DLA_AUTOROW", "stacked")

DEBUG_TOOLBAR = False

BPP_DODAWAJ_JEDNOSTKE_PRZY_ZAPISIE_PRACY = True

YARN_FILE_PATTERNS = {
    "jquery": ["dist/jquery.min.js"],
    "jqueryui": ["jquery-ui.min.js", "jquery-ui.css"],
    "what-input": ["dist/what-input.js"],
    "jquery.cookie": ["jquery.cookie.js"],
    "foundation-sites": [
        "dist/js/foundation.min.js",
        "dist/js/foundation.min.js.map",
        # testy
        "dist/css/normalize.min.css",
        "dist/css/foundation.min.css",
    ],
    "foundation-datepicker": [
        "foundation/fonts/*",
        "css/foundation-datepicker.min.css",
        "js/foundation-datepicker.min.js",
        "js/locales/foundation-datepicker.pl.js",
    ],
    "datatables.net": ["js/jquery.dataTables.js"],
    "datatables.net-zf": [
        "js/dataTables.foundation.js",
        "css/dataTables.foundation.css",
    ],
    "jinplace": ["js/jinplace.js"],
    "select2-foundation_theme": ["dist/select2-foundation-theme.css"],
    "kbw-keypad": ["dist/*"],
    # Zostana pozniej usuniete przez MANIFEST.in
    "qunit": ["qunit/qunit.js", "qunit/qunit.css"],
    "sinon": ["pkg/sinon.js"],
}


REST_FRAMEWORK = {
    # Use Django's standard `django.contrib.auth` permissions,
    # or allow read-only access for unauthenticated users.
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly"
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.LimitOffsetPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_THROTTLE_CLASSES": ("rest_framework.throttling.AnonRateThrottle",),
    "DEFAULT_THROTTLE_RATES": {"anon": "50/second",},
}
