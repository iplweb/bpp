import logging
import os
import pkgutil
import random
import string
import sys
from datetime import timedelta
from textwrap import dedent

import environ
import sentry_sdk
from django.core.exceptions import DisallowedHost, ImproperlyConfigured
from sentry_sdk.integrations.django import DjangoIntegration

from bpp.util import slugify_function

from django_bpp.version import VERSION

logger = logging.getLogger(__name__)

SCRIPT_PATH = os.path.abspath(os.path.dirname(__file__))

SITE_ROOT = os.path.abspath(os.path.join(SCRIPT_PATH, "..", ".."))

SECRET_KEY_UNSET = "Please set the DJANGO_BPP_SECRET_KEY variable."

# Ponieważ konieczna jest konfiguracja django-ldap-auth i potrzebne będą kolejne zmienne
# środowiskowe, ponieważ z Pipenv przeszedłem na poetry, ponieważ tych konfiguracji i
# serwerów (testowych, produkcyjnych) robi się coraz więcej -- z tych okazji zaczynam
# migrację konfiguracji na django-environ. Na ten moment przez django-environ pobiorę
# konfigurację LDAPa, docelowo przez django-environ powinna iść cała konfiguracja
# serwisu + docelowo będzie pewnie można zrezygnować z wielu plików konfiguracyjnych
# (local, test, production).


def int_or_none(v):
    try:
        return int(v)
    except ValueError:
        return None


env = environ.Env(
    # casting, default value
    #
    # LDAP
    #
    AUTH_LDAP_SERVER_URI=(str, None),
    # AUTH_LDAP_BIND_DN=(str, None),
    # AUTH_LDAP_BIND_PASSWORD=(str, None),
    # AUTH_LDAP_USER_SEARCH=(str, None),
    AUTH_LDAP_GROUP_SEARCH=(str, "ou=django,ou=groups,dc=auth,dc=local"),
    AUTH_LDAP_USER_SEARCH_QUERY=(str, "userPrincipalName=%(user)s@auth.local"),
    #
    # Microsoft Auth
    #
    MICROSOFT_AUTH_CLIENT_ID=(str, None),
    MICROSOFT_AUTH_CLIENT_SECRET=(str, None),
    MICROSOFT_AUTH_TENANT_ID=(str, None),
    MICROSOFT_AUTH_EXTRA_SCOPES=(str, ""),
    #
    # Email
    #
    EMAIL_URL=(str, "smtp://127.0.0.1:25"),
    DEFAULT_FROM_EMAIL=(str, "webmaster@localhost"),
    SERVER_EMAIL=(str, "root@localhost"),
    #
    # Administratorzy
    #
    ADMINS=(str, "Michał Pasternak <michal.dtz@gmail.com>"),
    #
    # Konfiguracja Sentry
    #
    SENTRYSDK_CONFIG_URL=(str, None),
    SENTRYSDK_TRACES_SAMPLE_RATE=(float, 0.2),
    #
    # Konfiguracja hosta Redisa
    #
    DJANGO_BPP_REDIS_HOST=(str, "localhost"),
    DJANGO_BPP_REDIS_PORT=(int, 6379),
    #
    # Konfiguracja baz Redisa (numerki)
    #
    DJANGO_BPP_REDIS_DB_BROKER=(int, 1),
    DJANGO_BPP_REDIS_DB_CELERY=(int, 2),
    DJANGO_BPP_REDIS_DB_SESSION=(int, 4),
    DJANGO_BPP_REDIS_DB_CACHE=(int, 5),
    DJANGO_BPP_REDIS_DB_LOCKS=(int, 6),
    #
    # Konfiguracja Django
    #
    DJANGO_BPP_HOSTNAME=(str, "localhost"),
    DJANGO_BPP_DB_NAME=(str, "bpp"),
    DJANGO_BPP_DB_USER=(str, "postgres"),
    DJANGO_BPP_DB_PASSWORD=(str, "password"),
    DJANGO_BPP_DB_HOST=(str, "localhost"),
    DJANGO_BPP_DB_PORT=(int, 5432),
    DJANGO_BPP_CONN_MAX_AGE=(int_or_none, 0),
    DJANGO_BPP_DB_DISABLE_SSL=(bool, False),
    DJANGO_BPP_SECRET_KEY=(str, SECRET_KEY_UNSET),
    DJANGO_BPP_MEDIA_ROOT=(str, os.path.join(os.getenv("HOME", "C:/"), "bpp-media")),
    #
    # Konfiguracja wymuszania zmiany haseł
    #
    DJANGO_BPP_USE_PASSWORD_HISTORY=(bool, True),
    DJANGO_BPP_PASSWORD_HISTORY_COUNT=(int, 12),
    #
    # Konfiguracja wygaszania sesji
    #
    DJANGO_BPP_SESSION_SECURITY_WARN_AFTER=(int, 540),
    DJANGO_BPP_SESSION_SECURITY_EXPIRE_AFTER=(int, 600),
    #
    # Konfiguracja BPP
    #
    DJANGO_BPP_UZYWAJ_PUNKTACJI_WEWNETRZNEJ=(bool, True),
    DJANGO_BPP_ENABLE_NEW_REPORTS=(int, 1),
    DJANGO_BPP_PUNKTUJ_MONOGRAFIE=(bool, True),
    #
    # Konfiguracja usług Google
    #
    DJANGO_BPP_GOOGLE_ANALYTICS_PROPERTY_ID=(str, None),
    DJANGO_BPP_GOOGLE_VERIFICATION_CODE=(str, "1111111111111111"),
    #
    # Konfiguracja widoczności opcji "Oświadczenie KEN"
    #
    DJANGO_BPP_POKAZUJ_OSWIADCZENIE_KEN=(bool, False),
    #
    # Statyczne pliki (CSS, JS, obrazki)
    #
    STATIC_ROOT=(str, os.path.abspath(os.path.join(SCRIPT_PATH, "..", "staticroot"))),
)

ENVFILE_PATHS = []

#
# Jeżeli NIE działąmy z site-packages, to prawdopodobnie działamy ze źródeł; w tej sytuacji skorzystaj z
# pliku .env w głównym katalogu repozytorium:
#
if "site-packages" not in __file__:
    ENVFILE_SOURCEDIR = os.path.abspath(os.path.join(SITE_ROOT, "..", ".env"))
    ENVFILE_PATHS.append(ENVFILE_SOURCEDIR)

#
# Kolejny plik w kolejności to plik w katalogu $HOME/.env oraz $HOME/.env.local:
#
ENVFILE_HOMEDIR = os.path.abspath(os.path.join(os.path.expanduser("~"), ".env"))
ENVFILE_PATHS.append(ENVFILE_HOMEDIR)
ENVFILE_PATHS.append(ENVFILE_HOMEDIR + ".local")

# Jeżeli zmienna jest zdefiniowana w więcej, niż jednym pliku to zmienna będzie nadpisana
# w kolejności plików:

for fn in ENVFILE_PATHS:
    if os.path.exists(fn) and os.path.isfile(fn):
        environ.Env.read_env(fn, overwrite=True)

#
# Ustaw Sentry
#


SENTRYSDK_CONFIG_URL = (
    env("SENTRYSDK_CONFIG_URL")
    or os.getenv("DJANGO_BPP_RAVEN_CONFIG_URL", None)
    or os.getenv("DJANGO_BPP_SENTRYSDK_CONFIG_URL", None)
)

PROCESS_INTERACTIVE = sys.stdin.isatty()

if SENTRYSDK_CONFIG_URL and not PROCESS_INTERACTIVE:
    # Ignore common errors
    def before_send(event, hint):
        if "exc_info" in hint:
            errors_to_ignore = (
                DisallowedHost,
                RuntimeError("Response content shorter than Content-Length"),
            )
            exc_value = hint["exc_info"][1]

            if isinstance(exc_value, errors_to_ignore):
                return None

        return event

    sentry_sdk.init(
        dsn=SENTRYSDK_CONFIG_URL,
        traces_sample_rate=env("SENTRYSDK_TRACES_SAMPLE_RATE"),
        integrations=[DjangoIntegration()],
        release=VERSION,
        before_send=before_send,
        send_default_pii=True,
    )

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

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [
            os.path.join(BASE_DIR, "templates"),
        ],
        "OPTIONS": {
            "loaders": [
                "admin_tools.template_loaders.Loader",
                "dbtemplates.loader.Loader",
                # Taka kolejnosc "laoders", i nie cache'ujemy tych dwóch powyżej, bo:
                # - dbtemplates ma swoje cacheowanie i uzywa wbudowanego backendu
                # - wbudowany backend domyslnie to 'locmem'
                # - jezeli uruchomie denorm_queue i serwer, to nie ma wymiany danych miedzy
                #   nimi obydwoma.
                # - pliki moga sie cache'owac, zarowno na testach jak i na produkcji,
                # - ... gdyz na testach jest DummyCacheBackend, a produkcja uzywa redis.
                # - rozchodzi sie o to, ze denorm_queue i reszta procesow musi miec podobna
                #   zawartosc cache-backendu,
                # - ... ktorej nie zapewni LocMem, bo on jest tylko na jeden proces.
                (
                    "django.template.loaders.cached.Loader",
                    [
                        "django.template.loaders.filesystem.Loader",
                        "django.template.loaders.app_directories.Loader",
                    ],
                ),
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
                "bpp.context_processors.config.bpp_configuration",
                "bpp.context_processors.global_nav.user",
                "bpp.context_processors.google_analytics.google_analytics",
                "cookielaw.context_processors.cookielaw",
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
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "password_policies.middleware.PasswordChangeMiddleware",
    "dj_pagination.middleware.PaginationMiddleware",
    "session_security.middleware.SessionSecurityMiddleware",
    "notifications.middleware.NotificationsMiddleware",
]

INTERNAL_IPS = ("127.0.0.1",)

ROOT_URLCONF = "django_bpp.urls"

# Python dotted path to the WSGI application used by Django's runserver.
WSGI_APPLICATION = "django_bpp.wsgi.application"


def _elem_in_sys_argv(possible):
    argv = " ".join(sys.argv)
    for elem in possible:
        if elem in argv:
            return True


TESTING = os.environ.get("DJANGO_BPP_TESTING", "") or _elem_in_sys_argv(
    [
        "jenkins",
        "py.test",
        "pytest",
        "helpers/pycharm/_jb_pytest_runner.py",
        "manage.py test",
    ]
)
MIGRATING = _elem_in_sys_argv(["makemigrations", "migrate"])

if TESTING:
    CELERY_ALWAYS_EAGER = True
    CELERY_TASK_ALWAYS_EAGER = True
    CELERY_EAGER_PROPAGATES_EXCEPTIONS = True

INSTALLED_APPS = [
    # "django_werkzeug",
    "daphne",
    "tinymce",
    "tee",
    "formtools",
    "denorm.apps.DenormAppConfig",
    "reversion",
    "djangoql",
    "cacheops",
    "channels",
    "dynamic_columns",
    "django.contrib.humanize",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.sitemaps",
    "django.contrib.postgres",
    "long_running",
    "import_pracownikow",
    "import_list_if",
    "password_policies",
    "create_test_db",
    "celery",
    "django_celery_results",
    "flexible_reports",
    "static_sitemaps",
    "cookielaw",
    "taggit",
    "columns",
    "zglos_publikacje.apps.ZglosPublikacjeConfig",
    "formdefaults.apps.FormdefaultsConfig",
    "raport_slotow",
    # Musi być PRZED django-autocomplete-light do momentu
    # dal 3.3.0-release, musi być naprawiony o ten błąd:
    # https://github.com/yourlabs/django-autocomplete-light/issues/981
    "bpp",
    "crossref_bpp",
    "pbn_api",
    "dal",
    "dal_select2",
    "grappelli",
    "django_bpp.apps.BppAdminConfig",  # replaced `django.contrib.admin`
    "tabular_permissions",
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
    "crispy_forms",
    "crispy_bootstrap5",
    "crispy_bootstrap3",  # dla django-rest-api HTML
    "crispy_forms_foundation",
    "compressor",
    "session_security",
    "notifications",
    "integrator2",
    "nowe_raporty",
    "rozbieznosci_dyscyplin",
    "loginas",
    "rozbieznosci_if",
    "robots",
    "webmaster_verification",
    "favicon",
    "miniblog",
    "import_dyscyplin",
    "mptt",
    "rest_framework",
    "django_filters",
    "api_v1",
    "adminsortable2",
    "import_export",
    "ewaluacja2021",
    # Zostawiamy - bezwarunkowo
    "test_bpp",
    #
    "dbtemplates",
    #
    "oswiadczenia",
    "import_polon",
    "import_list_ministerialnych",
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


# Ustawienia ModelBakery


def autoslug_gen():
    return "".join(
        random.choice(string.ascii_uppercase + string.digits) for _ in range(50)
    )


BAKER_CUSTOM_FIELDS_GEN = {"autoslug.fields.AutoSlugField": autoslug_gen}
BAKER_CUSTOM_CLASS = "bpp.tests.bpp_baker.BPP_Baker"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTOCOL", "https")

MAT_VIEW_REFRESH_COUNTDOWN = 30

STATIC_ROOT = env("STATIC_ROOT")

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

ALLOWED_HOSTS = [
    "127.0.0.1",
    "test.unexistenttld",
    env("DJANGO_BPP_HOSTNAME"),
]

CSRF_TRUSTED_ORIGINS = [
    "https://" + env("DJANGO_BPP_HOSTNAME"),
]

REDIS_HOST = env("DJANGO_BPP_REDIS_HOST")
REDIS_PORT = env("DJANGO_BPP_REDIS_PORT")

BROKER_URL = f"redis://{REDIS_HOST}:{REDIS_PORT}/{env('DJANGO_BPP_REDIS_DB_BROKER')}"
# CELERY_RESULT_BACKEND = BROKER_URL
CELERY_RESULT_BACKEND = "django-db"
CELERY_BROKER_URL = BROKER_URL

#
SESSION_REDIS_HOST = REDIS_HOST
SESSION_REDIS_PORT = REDIS_PORT
SESSION_REDIS_DB = env("DJANGO_BPP_REDIS_DB_SESSION")
SESSION_REDIS_PREFIX = "session"

ALLOWED_TAGS = ("b", "em", "i", "strong", "strike", "u", "sup", "font", "sub")

SESSION_SECURITY_PASSIVE_URLS = ["/messages/"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql_psycopg2",
        "NAME": env("DJANGO_BPP_DB_NAME"),
        "USER": env("DJANGO_BPP_DB_USER"),
        "PASSWORD": env("DJANGO_BPP_DB_PASSWORD"),
        "HOST": env("DJANGO_BPP_DB_HOST"),
        "PORT": env("DJANGO_BPP_DB_PORT"),
        "CONN_MAX_AGE": env("DJANGO_BPP_CONN_MAX_AGE"),
    },
}

if (DATABASES["default"]["HOST"] in ["localhost", "127.0.0.1"]) or (
    env("DJANGO_BPP_DB_DISABLE_SSL")
):
    options = DATABASES["default"].get("OPTIONS", {})
    options["sslmode"] = "disable"
    DATABASES["default"]["OPTIONS"] = options

SECRET_KEY = env("DJANGO_BPP_SECRET_KEY")

SENDFILE_URL = MEDIA_URL

# django-password-policies

# Zmiana hasla co 30 dni
PASSWORD_DURATION_SECONDS = int(
    os.getenv("DJANGO_BPP_PASSWORD_DURATION_SECONDS", str((60 * 60 * 24) * 30))
)

PASSWORD_USE_HISTORY = env("DJANGO_BPP_USE_PASSWORD_HISTORY")

PASSWORD_HISTORY_COUNT = env("DJANGO_BPP_PASSWORD_HISTORY_COUNT")

# wymagane przez django-password-policies
SESSION_SERIALIZER = "django.contrib.sessions.serializers.PickleSerializer"

MESSAGE_STORAGE = "messages_extends.storages.FallbackStorage"

TEST_NON_SERIALIZED_APPS = ["django.contrib.contenttypes", "django.contrib.auth"]

CELERYD_HIJACK_ROOT_LOGGER = False

CELERY_TRACK_STARTED = True

CELERYBEAT_SCHEDULE = {
    "cleanup-integrator2-files": {
        "task": "integrator2.tasks.remove_old_integrator_files",
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

MEDIA_ROOT = env("DJANGO_BPP_MEDIA_ROOT")

SENDFILE_ROOT = MEDIA_ROOT

GOOGLE_ANALYTICS_PROPERTY_ID = env("DJANGO_BPP_GOOGLE_ANALYTICS_PROPERTY_ID")

ROBOTS_SITEMAP_VIEW_NAME = "sitemap"

WEBMASTER_VERIFICATION = {"google": env("DJANGO_BPP_GOOGLE_VERIFICATION_CODE")}

EXCLUDE_FROM_MINIFYING = ["^google.*html$"]

SESSION_EXPIRE_AT_BROWSER_CLOSE = True

UZYWAJ_PUNKTACJI_WEWNETRZNEJ = env("DJANGO_BPP_UZYWAJ_PUNKTACJI_WEWNETRZNEJ")

THEME_NAME = os.getenv("DJANGO_BPP_THEME_NAME", "app-blue")

ENABLE_NEW_REPORTS = env("DJANGO_BPP_ENABLE_NEW_REPORTS")

SESSION_SECURITY_WARN_AFTER = env("DJANGO_BPP_SESSION_SECURITY_WARN_AFTER")

SESSION_SECURITY_EXPIRE_AFTER = env("DJANGO_BPP_SESSION_SECURITY_EXPIRE_AFTER")

PUNKTUJ_MONOGRAFIE = env("DJANGO_BPP_PUNKTUJ_MONOGRAFIE")

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
    "select2": [
        "dist/css/select2.min.css",
        "dist/js/select2.full.min.js",
        "dist/js/i18n/pl.js",
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
    # Nie limituj ilości zapytań (mpasternak, 6.06.2020) - jednakże, gdyby
    # trzeba było, to wystarczy odkomentować poniższe dwie linie:
    # "DEFAULT_THROTTLE_CLASSES": ("rest_framework.throttling.AnonRateThrottle",),
    # "DEFAULT_THROTTLE_RATES": {"anon": "50/second",},
}

BPP_WALIDUJ_AFILIACJE_AUTOROW = (
    os.getenv("DJANGO_BPP_WALIDUJ_AFILIACJE_AUTOROW", "tak") == "tak"
)

# ASGI_APPLICATION = "django_bpp.routing.application"
ASGI_APPLICATION = "django_bpp.asgi.application"

CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(REDIS_HOST, REDIS_PORT)],
        },
    },
}

#
# Domyślna konfiguracja logowania z Django 4.1, dodatek to logger
# django.console
#

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "require_debug_false": {
            "()": "django.utils.log.RequireDebugFalse",
        },
        "require_debug_true": {
            "()": "django.utils.log.RequireDebugTrue",
        },
    },
    "formatters": {
        "django.server": {
            "()": "django.utils.log.ServerFormatter",
            "format": "[{server_time}] {message}",
            "style": "{",
        }
    },
    "handlers": {
        "console": {
            "level": "INFO",
            "filters": ["require_debug_true"],
            "class": "logging.StreamHandler",
        },
        "console.always": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "stream": sys.stdout,
        },
        "django.server": {
            "level": "INFO",
            "class": "logging.StreamHandler",
            "formatter": "django.server",
        },
        "mail_admins": {
            "level": "ERROR",
            "filters": ["require_debug_false"],
            "class": "django.utils.log.AdminEmailHandler",
        },
    },
    "loggers": {
        "django": {
            "handlers": ["console", "mail_admins"],
            "level": "INFO",
        },
        "console.always": {
            "handlers": ["console.always"],
            "level": "INFO",
        },
        "django.server": {
            "handlers": ["django.server"],
            "level": "INFO",
            "propagate": False,
        },
        # Wypluwanie wszystkiego na konsolę, w tym tekstu z live-serverów
        # "": {  # Root logger
        #     "handlers": ["console"],
        #     "level": "INFO",
        # },
    },
}

# django-compressor dla każdej wersji będzie miał swoją nazwę katalogu
# wyjściowego, z tej prostej przyczyny, że nie wszystkie przeglądarki
# pamiętają, żeby odświeżyć cache:
COMPRESS_OUTPUT_DIR = f"CACHE-{VERSION}"

# django-tabular-permissions

TABULAR_PERMISSIONS_CONFIG = {
    "exclude": {
        "override": False,
        "apps": [
            "favicon",
            "taggit",
            "test_bpp",
            "rozbieznosci_if",
            "rozbieznosci_dyscyplin",
            "sessions",
            "sites",
            "contenttypes",
            "raport_slotow",
            "multiseek",
            "messages_extends",
            "menu",
            "sites",
            "robots",
            "pbn_api",
            "admin",
            "auth",
            "password_policies",
            "notifications",
            "dashboard",
            "django.contrib.contenttypes",
            "egeria",
            "eksport_pbn",
            "import_dyscyplin",
            "import_list_if",
            "import_pracownikow",
            "integrator2",
            "admin_tools",
        ],
        "models": [
            "bpp.cache_punktacja_autora",
            "bpp.cache_punktacja_autora_query",
            "bpp.cache_punktacja_autora_query_view",
            "bpp.cache_punktacja_autora_sum",
            "bpp.cache_punktacja_autora_sum_group_ponizej",
            "bpp.cache_punktacja_autora_sum_gruop",
            "bpp.cache_punktacja_autora_sum_ponizej",
            "bpp.cache_punktacja_dyscypliny",
            "bpp.sumy_wydawnictwo_zwarte_view",
            "bpp.opi_2012_afiliacja_do_wydzialu",
            "bpp.opi_2012_tytul_cache",
            "bpp.nowe_sumy_view",
            "bpp.autorzy",
            "bpp.rekord",
            "bpp.rekord_view",
            "bpp.autorzy_view",
        ],
        "function": "tabular_permissions.helpers.dummy_permissions_exclude",
    },
}

# PERMISSIONS_WIDGET_PATCH_GROUPADMIN = False
# PERMISSIONS_WIDGET_PATCH_USERADMIN = True

DBTEMPLATES_USE_REVERSION = True

DENORM_DISABLE_AUTOTIME_DURING_FLUSH = True
DENORM_AUTOTIME_FIELD_NAMES = [
    "ostatnio_zmieniony",
]

MAX_NO_AUTHORS_ON_BROWSE_JEDNOSTKA_PAGE = 500
"""
Maksymalna ilość autorów wyświetlanych w danej grupie na podstronie przeglądania danych jednostki. W przypadku
przekroczenia tej liczby, dana podgrupa autorów ("aktualni pracownicy","współpracowali kiedyś" itp) nie zostanie
wyświetlona.
"""

DEFAULT_AUTO_FIELD = "django.db.models.AutoField"

# django-import-export, używaj transakcji:
IMPORT_EXPORT_USE_TRANSACTIONS = True

# Maksymalna
BPP_MAX_ALLOWED_EXPORT_ITEMS = 1500

#
# Konfiguracja LDAP
#

AUTH_LDAP_SERVER_URI = env("AUTH_LDAP_SERVER_URI")

if AUTH_LDAP_SERVER_URI:
    AUTH_LDAP_BIND_DN = env("AUTH_LDAP_BIND_DN")
    AUTH_LDAP_BIND_PASSWORD = env("AUTH_LDAP_BIND_PASSWORD")

    try:
        import ldap
    except ImportError as e:
        raise ImproperlyConfigured(
            f"""W pliku konfiguracyjnym zdefiniowano zmienną AUTH_LDAP_SERVER_URI,
        co wskazuje na chęć skorzystania z autoryzacji serwerem LDAP. Niestety, biblioteka `ldap` języka
        Python nie jest możliwa do zaimportowania. Upewnij się, ze zainstalowano pakiet `bpp-iplweb[ldap]`.
        Wyjątek przy imporcie: {e}
        """
        )
    from django_auth_ldap.config import GroupOfNamesType, LDAPSearch

    AUTH_LDAP_USER_SEARCH = LDAPSearch(
        env("AUTH_LDAP_USER_SEARCH"),
        ldap.SCOPE_SUBTREE,
        env("AUTH_LDAP_USER_SEARCH_QUERY"),
    )

    # Set up the basic group parameters.
    AUTH_LDAP_GROUP_SEARCH = LDAPSearch(
        env("AUTH_LDAP_GROUP_SEARCH"),
        ldap.SCOPE_SUBTREE,
        "(objectClass=groupOfNames)",
    )
    AUTH_LDAP_GROUP_TYPE = GroupOfNamesType(name_attr="cn")

    AUTH_LDAP_GROUP_TYPE = GroupOfNamesType(name_attr="cn")

    # This is the default, but I like to be explicit.
    AUTH_LDAP_ALWAYS_UPDATE_USER = True

    # Use LDAP group membership to calculate group permissions.
    AUTH_LDAP_FIND_GROUP_PERMS = True

    # Cache distinguished names and group memberships for an hour to minimize
    # LDAP traffic.
    AUTH_LDAP_CACHE_TIMEOUT = 3600

    # Keep ModelBackend around for per-user permissions and maybe a local
    # superuser.
    AUTHENTICATION_BACKENDS = (
        "django_auth_ldap.backend.LDAPBackend",
        "django.contrib.auth.backends.ModelBackend",
    )

#
# Koniec konfiguracji LDAP
#

#
# Konfiguracja django-microsoft-auth (Office365)
#

MICROSOFT_AUTH_CLIENT_ID = env("MICROSOFT_AUTH_CLIENT_ID")

if MICROSOFT_AUTH_CLIENT_ID:
    try:
        import microsoft_auth  # noqa
    except ImportError as e:
        raise ImproperlyConfigured(
            dedent(
                f"""
                W pliku konfiguracyjnym zdefiniowano zmienną MICROSOFT_AUTH_CLIENT_ID,
                co wskazuje na chęć skorzystania z autoryzacji serwerem Microsoft (Office 365,
                Teams, etc). Niestety, biblioteka `microsoft_auth` języka Python nie jest
                możliwa do zaimportowania. Upewnij się, ze zainstalowano pakiet
                `bpp-iplweb[office365]`. Wyjątek przy próbie importu: {e}"""
            )
        )
    MICROSOFT_AUTH_CLIENT_SECRET = env("MICROSOFT_AUTH_CLIENT_SECRET")
    MICROSOFT_AUTH_TENANT_ID = env("MICROSOFT_AUTH_TENANT_ID")
    MICROSOFT_AUTH_LOGIN_TYPE = "ma"
    MICROSOFT_AUTH_EXTRA_SCOPES = env("MICROSOFT_AUTH_EXTRA_SCOPES")

    INSTALLED_APPS.append("microsoft_auth")
    TEMPLATES[0]["OPTIONS"]["context_processors"].append(
        "microsoft_auth.context_processors.microsoft",
    )

    AUTHENTICATION_BACKENDS = [
        "microsoft_auth.backends.MicrosoftAuthenticationBackend",
        "django.contrib.auth.backends.ModelBackend",
    ]

    # Konfiguracja w urls.py doda microsoft_auth.urls do ścieżki jezeli wykryje
    # aplikację `microsoft_auth` w INSTALLED_APPS

    # A teraz, ponieważ korzystamy z logowania przez microsoft_auth, wyłącz
    # polityki dotyczące haseł lokalnych. Problem polega na tym, że użytkownik po zalogowaniu
    # się przez microsoft_auth dostaje komunikat, że jego hasło uległo przeterminowaniu
    # i ma je zmienić...

    TEMPLATES[0]["OPTIONS"]["context_processors"].remove(
        "password_policies.context_processors.password_status"
    )
    MIDDLEWARE.remove("password_policies.middleware.PasswordChangeMiddleware")
    INSTALLED_APPS.remove("password_policies")

    logger.warning(
        "Używam autoryzacji microsoft_auth, wbudowana w BPP polityka haseł (zmiany, skomplikowanie)"
        " została wyłączona"
    )

#
# Koniec konfiguracji django-microsoft-auth
#

#
# Weryfikacja ilości backendów autoryzacyjnych.
#
# Zweryfikuj, ile backendów konfiguracyjnych jest skonfigurowanych. Jeżeli
# teoretycznie zbyt dużo, zwróć błąd:
#

if AUTH_LDAP_SERVER_URI and MICROSOFT_AUTH_CLIENT_ID:
    raise ImproperlyConfigured(
        """W pliku konfiguracyjnym jest określony zarówno parametry
    AUTH_LDAP_SERVER_URI jak i MICROSOFT_AUTH_CLIENT_ID. Na ten moment oprogramowanie BPP nie wie,
    co zrobić z listą backendów autoryzacyjnych. Skontaktuj się z autorem programu jeżeli potrzebujesz
    koniecznie obydwu, ewentualnie usuń tą linię z pliku konfiguracyjnego django_bpp/settings/base.py
    jeżeli faktycznie wiesz, co robisz. """
    )

#
# Koniec weryfikacji konfiguracji ilości backendów autoryzacyjnych
#


#
# Konfiguracja serwera pocztowego
#
EMAIL_CONFIG = env.email("EMAIL_URL")
vars().update(EMAIL_CONFIG)
SERVER_EMAIL = env("SERVER_EMAIL")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")

#
# Koniec konfiguracji serwera pocztowego
#

#
# Konta administratorów i managerów
#

from email.utils import getaddresses

ADMINS = getaddresses([env("ADMINS")])
MANAGERS = ADMINS

#
# Koniec konfiguracji kont administratora i managera
#

#
# django-easy-audit
#

#
# Uwaga: domyślnie easy-audit NIE jest włączony. Włącza go dopiero
# konfiguracja produkcyjna za pomocą poniższego kodu:
#
# INSTALLED_APPS.append("easyaudit")  # noqa
# MIDDLEWARE.append(  # noqa
#     "easyaudit.middleware.easyaudit.EasyAuditMiddleware",
# )
# DJANGO_EASY_AUDIT_PROPAGATE_EXCEPTIONS = True

DJANGO_EASY_AUDIT_WATCH_REQUEST_EVENTS = False
DJANGO_EASY_AUDIT_ADMIN_SHOW_REQUEST_EVENTS = False
DJANGO_EASY_AUDIT_READONLY_EVENTS = True
DJANGO_EASY_AUDIT_CRUD_DIFFERENCE_CALLBACKS = [
    "bpp.util.dont_log_anonymous_crud_events"
]
DJANGO_EASY_AUDIT_REGISTERED_CLASSES = [
    "zglos_publikacje.Zgloszenie_Publikacji",
    "bpp.Wydawnictwo_Zwarte",
    "bpp.Wydawnictwo_Ciagle",
    "bpp.Wydawnictwo_Zwarte_Streszczenie",
    "bpp.Wydawnictwo_Ciagle_Streszczenie",
    "bpp.Patent",
    "bpp.Praca_Doktorska",
    "bpp.Praca_Habilitacyjna",
    "bpp.Autor",
    "bpp.Autor_Jednostka",
    "bpp.Autor_Dyscyplina",
    "bpp.Jednostka",
    "bpp.Uczelnia",
    "bpp.Wydzial",
    "bpp.Zrodlo",
    "bpp.Jezyk",
    "bpp.Charakter_Formalny",
    "bpp.Typ_Odpowiedzialnosci",
    "bpp.Dyscyplina_Naukowa",
]

#
# Koniec django-easy-audit
#


SILENCED_SYSTEM_CHECKS.append("admin.E117")

DYNAMIC_COLUMNS_ALLOWED_IMPORT_PATHS = [
    "bpp.admin.wydawnictwo_ciagle",
    "bpp.admin.wydawnictwo_zwarte",
    "bpp.admin.autor",
]

DYNAMIC_COLUMNS_FORBIDDEN_COLUMN_NAMES = [
    ".*_cache$",
    ".*_sort$",
    "search_index",
    "legacy_data",
    "slug",
    "^cached_.*",
]

#
# Widoczność opcji "Oświadczenie KEN"
#

BPP_POKAZUJ_OSWIADCZENIE_KEN = env("DJANGO_BPP_POKAZUJ_OSWIADCZENIE_KEN")

#
# Dodanie modułów w namespace 'bpp_plugins' do INSTALLED_APPS
#


try:
    import bpp_plugins

    INSTALL_PLUGINS = True
except ImportError:
    INSTALL_PLUGINS = False

if INSTALL_PLUGINS:

    def iter_namespace(ns_pkg):
        return pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + ".")

    DISCOVERED_PLUGINS = [name for finder, name, ispkg in iter_namespace(bpp_plugins)]

    if DISCOVERED_PLUGINS:
        logger.info(
            "Znaleziono i aktywowano następujące pluginy BPP: %s", DISCOVERED_PLUGINS
        )

    [INSTALLED_APPS.append(x) for x in DISCOVERED_PLUGINS]

#
# TinyMCE
#
TINYMCE_DEFAULT_CONFIG = {
    "height": "320px",
    "width": "780px",
    "menubar": "file edit view insert format tools table help",
    "plugins": "advlist autolink lists link image charmap print preview anchor searchreplace visualblocks code "
    "fullscreen insertdatetime media table paste code help wordcount spellchecker",
    "toolbar": "undo redo | bold italic underline strikethrough | fontselect fontsizeselect formatselect | alignleft "
    "aligncenter alignright alignjustify | outdent indent |  numlist bullist checklist | forecolor "
    "backcolor casechange permanentpen formatpainter removeformat | pagebreak | charmap emoticons | "
    "fullscreen  preview save print | insertfile image media pageembed template link anchor codesample | "
    "a11ycheck ltr rtl | showcomments addcomment code",
}

#
# django-static-sitemaps
#

STATICSITEMAPS_PING_GOOGLE = False

#
# "Audyt" bezpieczeństwa
#

CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = True

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True

LANGUAGE_COOKIE_SECURE = True

X_FRAME_OPTIONS = "SAMEORIGIN"

STATICSITEMAPS_ROOT_DIR = os.path.relpath(STATIC_ROOT, os.getcwd())

DATA_UPLOAD_MAX_NUMBER_FIELDS = 5000
