import logging
import os
import pkgutil
import random
import re
import string
import sys
from datetime import timedelta
from email.utils import getaddresses
from textwrap import dedent

import environ
from celery.schedules import crontab
from django.core.exceptions import ImproperlyConfigured

from bpp.util import slugify_function
from django_bpp.channels_prefix import get_channels_prefix
from django_bpp.version import VERSION

logger = logging.getLogger(__name__)

SCRIPT_PATH = os.path.abspath(os.path.dirname(__file__))

SITE_ROOT = os.path.abspath(os.path.join(SCRIPT_PATH, "..", ".."))

SECRET_KEY_UNSET = "Please set the DJANGO_BPP_SECRET_KEY variable."
ALTCHA_HMAC_KEY_UNSET = "Please set the ALTCHA_HMAC_KEY variable."


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
    #
    # Theme
    #
    DJANGO_BPP_THEME_NAME=(str, "app-green"),
    #
    # Konfiguracja hosta Redisa
    #
    DJANGO_BPP_REDIS_HOST=(str, "localhost"),
    DJANGO_BPP_REDIS_PORT=(int, 6379),
    #
    # Konfiguracja baz Redisa (numerki)
    #
    DJANGO_BPP_REDIS_DB_BROKER=(int, 1),  # Celery broker
    DJANGO_BPP_REDIS_DB_CELERY=(int, 2),
    DJANGO_BPP_REDIS_DB_SESSION=(int, 4),
    DJANGO_BPP_REDIS_DB_CACHE=(int, 5),
    DJANGO_BPP_REDIS_DB_LOCKS=(int, 6),
    DJANGO_BPP_REDIS_DB_CACHEOPS=(int, 7),
    #
    # Konfiguracja Django
    #
    DJANGO_BPP_HOSTNAME=(str, "localhost"),
    # Multi-hosted: comma-separated lista nazw hostów (np. "u1.example,u2.example").
    # Pusta wartość = używaj DJANGO_BPP_HOSTNAME (single-host, backward compat).
    DJANGO_BPP_HOSTNAMES=(str, ""),
    DJANGO_BPP_DB_NAME=(str, "bpp"),
    DJANGO_BPP_DB_USER=(str, "bpp"),
    DJANGO_BPP_DB_PASSWORD=(str, "password"),
    DJANGO_BPP_DB_HOST=(str, "localhost"),
    DJANGO_BPP_DB_PORT=(int, 5432),
    DJANGO_BPP_CONN_MAX_AGE=(int_or_none, 0),
    DJANGO_BPP_DB_DISABLE_SSL=(bool, False),
    DJANGO_BPP_TEST_TEMPLATE=(str, ""),
    DJANGO_BPP_SECRET_KEY=(str, SECRET_KEY_UNSET),
    ALTCHA_HMAC_KEY=(str, ALTCHA_HMAC_KEY_UNSET),
    ZGLOS_CAPTCHA_ENABLED=(bool, False),
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
    DJANGO_BPP_GOOGLE_ANALYTICS_PROPERTY_ID=(str, ""),
    DJANGO_BPP_GOOGLE_VERIFICATION_CODE=(str, "1111111111111111"),
    #
    # Konfiguracja widoczności opcji "Oświadczenie KEN"
    #
    DJANGO_BPP_POKAZUJ_OSWIADCZENIE_KEN=(bool, False),
    #
    # Statyczne pliki (CSS, JS, obrazki)
    #
    STATIC_ROOT=(str, os.path.abspath(os.path.join(SCRIPT_PATH, "..", "staticroot"))),
    #
    # Wyświetlanie nazwy wydziału przez jednostki
    #
    DJANGO_BPP_SKROT_WYDZIALU_W_NAZWIE_JEDNOSTKI=(bool, True),
    #
    # Ile dni trzymać wyniki działań Celery - domyślnie tydzień
    #
    CELERY_RESULT_EXPIRES_DAYS=(int, 7),
    #
    # Maksymalna ilość eksportowanych wierszy z Admina
    #
    DJANGO_BPP_MAX_ALLOWED_EXPORT_ITEMS=(int, 1500),
    #
    # Serwer testowy -- ustaw to na True
    #
    DJANGO_BPP_ENABLE_TEST_CONFIGURATION=(bool, False),
    #
    # Rollbar access settings
    #
    ROLLBAR_ACCESS_TOKEN=(str, None),
    # Publiczny token klienta (post_client_item) do frontendowego Rollbara.
    ROLLBAR_CLIENT_ACCESS_TOKEN=(str, ""),
    #
    # Prometheus
    #
    DJANGO_BPP_ENABLE_PROMETHEUS=(bool, False),
    #
    # Liczniki w filtrac
    #
    DYNAMIC_FILTER_COUNTS_ENABLE=(bool, True),
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

if not os.environ.get("DJANGO_BPP_SKIP_DOTENV"):
    for fn in ENVFILE_PATHS:
        if os.path.exists(fn) and os.path.isfile(fn):
            environ.Env.read_env(fn, overwrite=True)

#
# Czy proces jest interaktywny?
#

PROCESS_INTERACTIVE = sys.stdin.isatty()

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

TIME_ZONE = "Europe/Warsaw"
LANGUAGE_CODE = "pl"
LANGUAGES = (("pl", "Polish"),)

LOCALE_PATHS = [
    os.path.join(BASE_DIR, "locale"),
]

# SITE_ID służy jako fallback dla SiteResolutionMiddleware gdy hostname
# nie pasuje do żadnego obiektu Site. W multi-hosted ustawia się na ID
# domyślnego Site. static-sitemaps również wymaga tej wartości.
SITE_ID = env("DJANGO_BPP_SITE_ID", default=1, cast=int)
USE_I18N = True
USE_TZ = True

# URL usługi html2docx (sidecar HTTP) używanej jako fallback konwersji DOCX,
# gdy pandoc zawiedzie (np. core dump na VMWare ESX). None => fallback
# wyłączony, degradacja miękka (DocxConversionError). Patrz
# nowe_raporty.docx_export._convert_using_html2docx_service.
HTML2DOCX_URL = env("DJANGO_BPP_HTML2DOCX_URL", default=None)

# Django 5.0 transitional; stanie się domyślne w 6.0. Wycisza
# RemovedInDjango60Warning z forms.URLField dla URL-i bez schematu.
FORMS_URLFIELD_ASSUME_HTTPS = True

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

# Storage backends (Django 5.x). `staticfiles` → tolerancyjny
# ManifestStaticFilesStorage (issue #269): content-hash cache-busting całego
# long-taila statyków; szczegóły i powód tolerancji w django_bpp/storage.py.
# `default` (media) zostaje na domyślnym Django FileSystemStorage.
STORAGES = {
    "default": {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    },
    "staticfiles": {
        "BACKEND": "django_bpp.storage.TolerantManifestStaticFilesStorage",
    },
}

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
                "django_bpp.context_processors.conditional_password_status",
                "bpp.context_processors.uczelnia.uczelnia",
                "bpp.context_processors.config.bpp_configuration",
                "bpp.context_processors.constance_config.constance_config",
                "bpp.context_processors.global_nav.user",
                "bpp.context_processors.google_analytics.google_analytics",
                "bpp.context_processors.rollbar.rollbar_client",
                "bpp.context_processors.pbn_token_aktualny.pbn_token_aktualny",
                "bpp.context_processors.microsoft_auth.microsoft_auth_status",
                "bpp.context_processors.orcid.orcid_auth_status",
                "bpp.context_processors.oidc.oidc_auth_status",
                "bpp.context_processors.external_auth.external_auth_status",
                "bpp.context_processors.testing.testing",
                "cookielaw.context_processors.cookielaw",
                "django_countdown.context_processors.countdown_context",
                "nowe_raporty.menu.raporty_menu",
            ],
        },
    },
]

MIDDLEWARE = [
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "bpp.middleware.MaliciousRequestBlockingMiddleware",  # Block malicious requests (pagination, PHP, .git, etc.) early
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "bpp.middleware.SiteResolutionMiddleware",  # After auth - resolves Site/Uczelnia from hostname
    "django_countdown.middleware.CountdownBlockingMiddleware",  # After auth - needs request.user
    "first_run_wizard.middleware.FirstRunWizardMiddleware",  # After auth middleware to have request.user
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "django_bpp.middleware.ConditionalPasswordChangeMiddleware",
    "dj_pagination.middleware.PaginationMiddleware",
    "session_security.middleware.SessionSecurityMiddleware",
    "bpp.middleware.NotificationsMiddleware",
    # 'rollbar.contrib.django.middleware.RollbarNotifierMiddleware',
    "bpp.middleware.CustomRollbarNotifierMiddleware",
    "oauth_mcp.middleware.ApiReadOnlyForBearerMiddleware",
    # AxesMiddleware MUSI być ostatnie — przechwytuje AxesBackendPermissionDenied
    # z backendu logowania i renderuje odpowiedź "konto zablokowane".
    "axes.middleware.AxesMiddleware",
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
    # bpp_setup_wizard BEFORE first_run_wizard so BPP-side templates
    # (first_run_wizard/admin_user.html in bpp_setup_wizard.templates)
    # override the vendor-neutral defaults shipped by the package.
    "bpp_setup_wizard",  # BPP-specific step + BPP-styled templates
    "first_run_wizard",  # Pluggable first-run wizard engine (PyPI)
    "daphne",
    "tinymce",
    "django_polish_inflection",
    "formtools",
    "denorm.apps.DenormAppConfig",
    "reversion",
    "reversion_compare",
    "djangoql",
    "cacheops",
    "constance",
    "constance.backends.database",
    "channels",
    "dynamic_admin_columns",
    "django.contrib.humanize",
    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django_countdown",  # System odliczania do zamknięcia serwisu
    "django.contrib.sitemaps",
    "django.contrib.postgres",
    "long_running",
    "import_pracownikow",
    "import_list_if",
    "password_policies",
    "axes",  # Ochrona przed brute-force logowaniem (lockout po nieudanych próbach)
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
    "ranking_autorow",
    # Musi być PRZED django-autocomplete-light do momentu
    # dal 3.3.0-release, musi być naprawiony o ten błąd:
    # https://github.com/yourlabs/django-autocomplete-light/issues/981
    "bpp",
    "crossref_bpp",
    "pbn_api",
    "dspace_api",
    "pbn_export_queue",
    "pbn_komparator_zrodel",
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
    "powiazania_autorow",
    "compressor",
    "session_security",
    "channels_broadcast",
    "liveops",
    "integrator2",
    "nowe_raporty",
    "rozbieznosci_dyscyplin",
    "loginas",
    "rozbieznosci",
    "webmaster_verification",
    "favicon",
    "miniblog",
    "siteblog",
    "import_dyscyplin",
    "mptt",
    "rest_framework",
    "oauth_mcp",
    "oauth2_provider",
    "django_filters",
    "api_v1",
    "adminsortable2",
    "import_export",
    "ewaluacja_common",
    "ewaluacja2021",
    "ewaluacja_liczba_n",
    "ewaluacja_metryki",
    "ewaluacja_optymalizacja",
    "ewaluacja_optymalizuj_publikacje",
    "ewaluacja_dwudyscyplinowcy",
    # UWAGA: NIE USUWAĆ aplikacji test_bpp z INSTALLED_APPS!
    #
    # Mimo nazwy sugerującej "tylko do testów", test_bpp dostarcza realnych
    # modeli Django (TestOperation, TestObjectThatDoesNotExist) używanych przez
    # testy aplikacji `long_running`. Aplikacja `long_running` operuje na
    # modelach przez ContentType i wymaga prawdziwych tabel w bazie danych —
    # tych modeli nie da się zastąpić mockami.
    #
    # Aplikacja MUSI być zarejestrowana bezwarunkowo (również w produkcji),
    # bo baseline.sql oraz migracje zakładają istnienie tabel
    # test_bpp_testoperation oraz test_bpp_testobjectthatdoesnotexist.
    # W produkcji tabele pozostają puste i nieużywane — narzut = 0.
    #
    # Pełny opis: src/test_bpp/README.md
    "test_bpp",
    #
    "dbtemplates",
    #
    "oswiadczenia",
    "komparator_pbn",
    "import_polon",
    "import_list_ministerialnych",
    "import_punktacji_zrodel",
    "snapshot_odpiec",
    "stan_systemu",
    "deduplikator_autorow",
    "deduplikator_publikacji",
    "deduplikator_zrodel",
    "importer_autorow_pbn",
    "przemapuj_prace_autora",
    "przemapuj_zrodla_pbn",
    "przemapuj_zrodlo",
    "pbn_downloader_app",
    "pbn_wysylka_oswiadczen",
    "pbn_integrator",
    "pbn_import",
    "orcid_integration",
    "komparator_pbn_udzialy",
    "komparator_publikacji_pbn",
    "admin_dashboard",
    "importer_publikacji",
    "import_sqlite",
    "django_pg_baseline",
]

PG_BASELINE = {
    "BASELINE_DIR": os.path.abspath(os.path.join(SITE_ROOT, "..", "baseline-sql")),
    # Our image has plpython3u + pl_PL.UTF-8 locale — vanilla postgres doesn't.
    "REBUILD_IMAGE": "iplweb/bpp_dbserver:psql-16.13",
    # bpp-specific exclusions on top of the generic django_session default.
    "PG_DUMP_EXTRA_EXCLUDE_TABLE_DATA": [
        "django_cache*",
        "easy_thumbnails_*",
        # nowe_raporty seeds default reports via a post_migrate handler
        # (NoweRaportyConfig.ready -> seed_reports/create_entries), which fires
        # during a baseline rebuild because that runs migrate with TESTING=False.
        # That application data must NOT live in the schema baseline: the dump is
        # loaded as-is into every test DB, and the nowe_raporty tests assume these
        # tables start empty. Production is unaffected — post_migrate re-seeds
        # idempotently on a real deploy. See nowe_raporty/seeding/.
        "flexible_reports_*",
        "nowe_raporty_definicjaraportu*",
    ],
    # dbtemplates inserts rows via data-migration — we keep them in the
    # dump, but freeze their timestamps for a deterministic diff.
    "FREEZE_TIMESTAMPS_EXTRA": [
        ("django_template", ["creation_date", "last_changed"]),
    ],
}

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


BAKER_CUSTOM_FIELDS_GEN = {
    "autoslug.fields.AutoSlugField": autoslug_gen,
    "django.contrib.postgres.fields.array.ArrayField": lambda: [],
    "django.contrib.postgres.search.SearchVectorField": lambda: None,
}
BAKER_CUSTOM_CLASS = "bpp.tests.bpp_baker.BPP_Baker"

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTOCOL", "https")

MAT_VIEW_REFRESH_COUNTDOWN = 30

STATIC_ROOT = env("STATIC_ROOT")

COMPRESS_CSS_FILTERS = [
    "compressor.filters.css_default.CssAbsoluteFilter",
    "compressor.filters.cssmin.CSSMinFilter",
]
# Bez filtra JS: wszystkie nietrywialne wejscia (bundle.js itd.) sa juz
# zminifikowane przez esbuild na etapie grunt build. rJSMinFilter
# re-minifikowal 1,5 MB bundle'a przy `manage.py compress` na starcie
# kontenera (zysk ~0 bajtow), a regexowe minifikatory potrafia zepsuc
# nowoczesna skladnie emitowana przez AST-owy esbuild. {% compress js %}
# zostaje — daje konkatenacje + hashowane nazwy plikow (cache-busting).
COMPRESS_JS_FILTERS = []

COMPRESS_ROOT = STATIC_ROOT

# Jedyne źródło prawdy dla listy motywów kolorystycznych front-endu:
# (wartość pliku SCSS bez rozszerzenia, etykieta widoczna w adminie uczelni).
# Admin (UczelniaAdminForm) czyta tę listę, a COMPRESS_OFFLINE_CONTEXT poniżej
# jest z niej wyliczany — dodanie motywu = jeden wpis tutaj (+ ręcznie target
# w Gruntfile.js). Walidacja wyboru żyje w formularzu, NIE w `choices` pola
# modelu, dzięki czemu zmiana listy nie wymaga migracji.
BPP_THEMES = [
    ("app-green", "Zielony"),
    ("app-blue", "Niebieski"),
    ("app-orange", "Pomarańczowy"),
    ("app-vizja", "Bursztynowo-granatowy (VIZJA)"),
    ("app-mwsl", "Pomarańczowo-granatowy (MWSL)"),
    ("app-uafm", "Czerwono-błękitny (UAFM)"),
]

COMPRESS_OFFLINE_CONTEXT = [
    {
        "THEME_NAME": f"scss/{value}.css",
        "STATIC_URL": STATIC_URL,
        "LANGUAGE_CODE": "pl",
    }
    for value, _label in BPP_THEMES
]

# Lista hostów obsługiwanych przez deployment.
# Konfiguracja jawnie XOR: ustaw ALBO DJANGO_BPP_HOSTNAME (single, bez
# przecinka), ALBO DJANGO_BPP_HOSTNAMES (multi-host, CSV z minimum dwoma
# hostami). Ustawienie obu = ImproperlyConfigured (intencja niejasna).
_hostname = os.environ.get("DJANGO_BPP_HOSTNAME", "").strip()
_hostnames_csv = os.environ.get("DJANGO_BPP_HOSTNAMES", "").strip()

if _hostname and _hostnames_csv:
    raise ImproperlyConfigured(
        "Ustaw albo DJANGO_BPP_HOSTNAME (single host, bez przecinka), albo "
        "DJANGO_BPP_HOSTNAMES (multi-host, comma-separated, minimum dwa). "
        "Oba naraz są niejednoznaczne — wybierz jedno."
    )

if _hostnames_csv:
    if "," not in _hostnames_csv:
        raise ImproperlyConfigured(
            f"DJANGO_BPP_HOSTNAMES musi zawierać minimum dwa hosty "
            f"oddzielone przecinkiem (otrzymano: {_hostnames_csv!r}). "
            f"Dla single-host użyj DJANGO_BPP_HOSTNAME."
        )
    DJANGO_BPP_HOSTNAMES = [h.strip() for h in _hostnames_csv.split(",") if h.strip()]
    if len(DJANGO_BPP_HOSTNAMES) < 2:
        raise ImproperlyConfigured(
            f"DJANGO_BPP_HOSTNAMES po sparsowaniu daje mniej niż dwa hosty "
            f"(otrzymano: {DJANGO_BPP_HOSTNAMES!r}). "
            f"Dla single-host użyj DJANGO_BPP_HOSTNAME."
        )
elif _hostname:
    if "," in _hostname:
        raise ImproperlyConfigured(
            f"DJANGO_BPP_HOSTNAME nie może zawierać przecinka "
            f"(otrzymano: {_hostname!r}). Dla multi-host użyj "
            f"DJANGO_BPP_HOSTNAMES."
        )
    DJANGO_BPP_HOSTNAMES = [_hostname]
else:
    # Żadne nie ustawione — fallback do default ("localhost") z env declaration
    DJANGO_BPP_HOSTNAMES = [env("DJANGO_BPP_HOSTNAME")]

# Canonical/primary hostname — pierwszy z listy. Używany m.in. przez
# Rollbar jako identyfikacja deployment'u (oznaczenie instalacji); per-request
# vhost gdzie padło zgłoszenie ma osobny klucz w extra_data middleware'u.
DJANGO_BPP_HOSTNAME = DJANGO_BPP_HOSTNAMES[0]

ALLOWED_HOSTS = [
    "127.0.0.1",
    "appserver",
    "appserver:8000",
    "test.unexistenttld",
    *DJANGO_BPP_HOSTNAMES,
]

CSRF_TRUSTED_ORIGINS = ["https://" + h for h in DJANGO_BPP_HOSTNAMES]

# Optional extra CSRF origins for dev with non-standard ports
# (comma-separated, e.g. "https://bpp.localnet:10443,https://localhost:10443")
DJANGO_BPP_CSRF_EXTRA_ORIGINS = env("DJANGO_BPP_CSRF_EXTRA_ORIGINS", default="")
if DJANGO_BPP_CSRF_EXTRA_ORIGINS:
    CSRF_TRUSTED_ORIGINS.extend(
        origin.strip()
        for origin in DJANGO_BPP_CSRF_EXTRA_ORIGINS.split(",")
        if origin.strip()
    )

REDIS_HOST = env("DJANGO_BPP_REDIS_HOST")
REDIS_PORT = env("DJANGO_BPP_REDIS_PORT")

CELERY_BROKER_URL = (
    f"redis://{REDIS_HOST}:{REDIS_PORT}/{env('DJANGO_BPP_REDIS_DB_BROKER')}"
)
CELERY_RESULT_BACKEND = (
    f"redis://{REDIS_HOST}:{REDIS_PORT}/{env('DJANGO_BPP_REDIS_DB_CELERY')}"
)
BROKER_URL = CELERY_BROKER_URL  # legacy alias for any third-party code

CELERY_BROKER_TRANSPORT_OPTIONS = {
    # Redis re-delivers in-flight task after this timeout if worker dies;
    # must exceed longest job (PBN export, POLON import).
    "visibility_timeout": 3600 * 6,
}

CELERY_RESULT_EXTENDED = False
CELERY_RESULT_EXPIRES = timedelta(days=env("CELERY_RESULT_EXPIRES_DAYS"))

CELERYD_HIJACK_ROOT_LOGGER = False

CELERY_TRACK_STARTED = False

# Workerzy emituja eventy lifecycle (online/heartbeat/offline + task-received/
# started/succeeded/failed) na brokerze. Bez tego Flower nie widzi workerow.
CELERY_WORKER_SEND_TASK_EVENTS = True

# --- Importer publikacji ---------------------------------------------------
# Watchdog sesji importu: sesja w stanie in-flight (FETCHING/CREATING) dłużej
# niż tyle sekund jest uznawana za martwą (zgubiony/ubity worker Celery — task
# nie wykona bloku except) i przy kolejnym pollu przełączana na IMPORT_FAILED.
# Patrz importer_publikacji.models.ImportSession.is_stalled(). Świadomie duży
# margines, żeby nie ubijać legalnie długiego dopasowania autorów.
IMPORTER_STALL_TIMEOUT = env("IMPORTER_STALL_TIMEOUT", default=180, cast=int)

# Twardy timeout (sekundy) requestu HTTP do API CrossRef przy pobieraniu DOI.
# Bez tego obowiązuje domyślny 30 s biblioteki `crossref` — ustawiamy jawnie,
# żeby był widoczny i konfigurowalny. Patrz crossref_bpp.models.
CROSSREF_API_TIMEOUT = env("CROSSREF_API_TIMEOUT", default=30, cast=int)

# Retencja (w dniach) plików XLS importu pracowników. Komenda zarządzająca
# `usun_stare_pliki_importu_pracownikow` kasuje blob `plik_xls` importów
# starszych niż tyle dni, zostawiając sam rekord i wiersze (historia
# dopasowań pozostaje dostępna, plik źródłowy nie).
# Patrz import_pracownikow.management.commands.usun_stare_pliki_importu_pracownikow.
IMPORT_PRACOWNIKOW_RETENCJA_DNI = env(
    "IMPORT_PRACOWNIKOW_RETENCJA_DNI", default=90, cast=int
)

CELERY_ROUTES = [
    {"denorm.tasks.flush_single": {"queue": "denorm"}},
]

CELERYBEAT_SCHEDULE = {
    "cleanup-integrator2-files": {
        "task": "integrator2.tasks.remove_old_integrator_files",
        "schedule": timedelta(days=1),
    },
    "zaktualizuj-liczbe-cytowan": {
        "task": "bpp.tasks.zaktualizuj_liczbe_cytowan",
        "schedule": timedelta(days=5),
    },
    "pbn-api-kolejka-wyczysc-wpisy-bez-rekordow": {
        "task": "pbn_api.tasks.kolejka_wyczysc_wpisy_bez_rekordow",
        "schedule": timedelta(days=7),
    },
    "scan-for-duplicates-daily": {
        "task": "deduplikator_autorow.scan_for_duplicates",
        "schedule": crontab(hour=3, minute=0),  # Daily at 3 AM
    },
    "cleanup-oswiadczenia-export-files": {
        "task": "oswiadczenia.tasks.remove_old_oswiadczenia_export_files",
        "schedule": timedelta(days=1),
    },
    # Retencja porzuconych plików tmp kreatora zgłoszeń publikacji (anonimowy
    # formularz — porzucone uploady zostałyby na wolumenie media bez ograniczeń;
    # anty-DoS na dysk, bpp #551). Kasuje sieroty >24h z osobnego katalogu tmp,
    # nie ruszając finalnych załączników. Worker montuje media (jak sąsiednie
    # cleanup-*), więc kasowanie działa.
    "wyczysc-zglos-tmp-pliki": {
        "task": "zglos_publikacje.tasks.wyczysc_zglos_tmp_pliki",
        "schedule": timedelta(hours=6),
    },
    "rebuild-pbn-author-match-cache": {
        "task": "importer_autorow_pbn.tasks.auto_rebuild_match_cache_task",
        "schedule": crontab(hour=3, minute=30),  # Daily at 3:30 AM
    },
    "pbn-export-queue-watchdog": {
        "task": "pbn_export_queue.tasks.queue_watchdog",
        "schedule": timedelta(minutes=10),
    },
    "pbn-export-queue-report-technical-errors": {
        "task": "pbn_export_queue.tasks.report_technical_errors_to_rollbar",
        "schedule": crontab(hour=8, minute=0),  # Daily at 8 AM
    },
    "powiazania-autorow-przelicz-codziennie": {
        "task": "powiazania_autorow.calculate_author_connections",
        "schedule": crontab(hour=4, minute=0),  # Daily at 4 AM
    },
    # Retencja logów logowania (RODO): kasuj LoginEvent starsze niż 24 mies.
    # Raz w miesiącu, 1. dnia o 2:00. CRUDEvent (historia edycji) NIE jest
    # ruszany.
    "easyaudit-purge-stare-logi-logowania": {
        "task": "bpp.tasks.usun_stare_logi_logowania_easyaudit",
        "schedule": crontab(hour=2, minute=0, day_of_month=1),
    },
}


#
SESSION_REDIS_HOST = REDIS_HOST
SESSION_REDIS_PORT = REDIS_PORT
SESSION_REDIS_DB = env("DJANGO_BPP_REDIS_DB_SESSION")
SESSION_REDIS_PREFIX = "session"

ALLOWED_TAGS = ("b", "em", "i", "strong", "strike", "u", "sup", "font", "sub")

SESSION_SECURITY_PASSIVE_URLS = ["/messages/"]

DATABASES = {
    "default": {
        # "ENGINE": "django.db.backends.postgresql_psycopg2",
        "ENGINE": "django_bpp.db_connclosed_fix",
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

# Pozwól pluginowi testcontainers (i potencjalnie innym setupom) zażądać
# stworzenia testowej bazy jako klonu bazy źródłowej:
# CREATE DATABASE test_bpp WITH TEMPLATE <template>. Używane by
# preloadowany baseline (mountowany do /docker-entrypoint-initdb.d/
# w kontenerze) został natychmiast dostępny dla testów bez ponownego
# uruchamiania psql.
_test_template = env("DJANGO_BPP_TEST_TEMPLATE")
if _test_template:
    test_settings = DATABASES["default"].get("TEST", {})
    test_settings["TEMPLATE"] = _test_template
    DATABASES["default"]["TEST"] = test_settings

SECRET_KEY = env("DJANGO_BPP_SECRET_KEY")

# ALTCHA — proof-of-work CAPTCHA na anonimowym formularzu zgłoszeń publikacji.
# Model klucza jak SECRET_KEY: sentinel default, realny klucz z env (auto-gen
# w bpp-deploy). Captcha domyślnie WYŁĄCZONA (opt-in). Brak hard-raise — miękki
# system-check WARNING (zglos_publikacje/checks.py) sygnalizuje placeholder.
ALTCHA_HMAC_KEY = env("ALTCHA_HMAC_KEY")
ZGLOS_CAPTCHA_ENABLED = env("ZGLOS_CAPTCHA_ENABLED")
INSTALLED_APPS += ["django_altcha"]

# Klucz Fernet do szyfrowania sekretów integracji (DSpace itd.).
# Wygeneruj: python -c "from cryptography.fernet import Fernet;
#   print(Fernet.generate_key().decode())"
DSPACE_CREDENTIALS_KEY = env("DSPACE_CREDENTIALS_KEY", default="")

SENDFILE_URL = MEDIA_URL

# django-password-policies

# Zmiana hasla co 30 dni
PASSWORD_DURATION_SECONDS = int(
    os.getenv("DJANGO_BPP_PASSWORD_DURATION_SECONDS", str((60 * 60 * 24) * 30))
)

PASSWORD_USE_HISTORY = env("DJANGO_BPP_USE_PASSWORD_HISTORY")

PASSWORD_HISTORY_COUNT = env("DJANGO_BPP_PASSWORD_HISTORY_COUNT")

SESSION_SERIALIZER = "django.contrib.sessions.serializers.JSONSerializer"

MESSAGE_STORAGE = "messages_extends.storages.FallbackStorage"

TEST_NON_SERIALIZED_APPS = ["django.contrib.contenttypes", "django.contrib.auth"]


def can_login_as(request, target_user):
    return request.user.is_superuser


CAN_LOGIN_AS = can_login_as

#

MEDIA_ROOT = env("DJANGO_BPP_MEDIA_ROOT")

SENDFILE_ROOT = MEDIA_ROOT

GOOGLE_ANALYTICS_PROPERTY_ID = env("DJANGO_BPP_GOOGLE_ANALYTICS_PROPERTY_ID")

WEBMASTER_VERIFICATION = {"google": env("DJANGO_BPP_GOOGLE_VERIFICATION_CODE")}

SESSION_EXPIRE_AT_BROWSER_CLOSE = True

UZYWAJ_PUNKTACJI_WEWNETRZNEJ = env("DJANGO_BPP_UZYWAJ_PUNKTACJI_WEWNETRZNEJ")

THEME_NAME = env("DJANGO_BPP_THEME_NAME")

ENABLE_NEW_REPORTS = env("DJANGO_BPP_ENABLE_NEW_REPORTS")

SESSION_SECURITY_WARN_AFTER = env("DJANGO_BPP_SESSION_SECURITY_WARN_AFTER")

SESSION_SECURITY_EXPIRE_AFTER = env("DJANGO_BPP_SESSION_SECURITY_EXPIRE_AFTER")

PUNKTUJ_MONOGRAFIE = env("DJANGO_BPP_PUNKTUJ_MONOGRAFIE")


# dla django-model-utils SplitField. BPP używa „<!-- tutaj -->” zamiast
# upstream-owego „<!-- split -->”, więc help_text na siteblog.Article.article_body
# różni się od tego zaszytego w siteblog/0001_initial. To no-op drift —
# `makemigrations siteblog` bez argumentów wygeneruje 0002_alter_article_body
# w site-packages (ALTER TABLE jest no-op, bo help_text nie wpływa na schemat).
# Plik nigdy nie trafia do git, prod-`migrate` go nie zaaplikuje (nie istnieje
# w pakiecie). Ignoruj i nie commituj.
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
    "jquery-circle-progress": ["dist/circle-progress.min.js"],
    "select2-foundation-theme": ["dist/select2-foundation-theme.css"],
    "plotly.js": ["dist/plotly.min.js", "dist/plotly-locale-pl.js"],
    "htmx.org": ["dist/htmx.js"],
    "tone": ["build/Tone.js", "build/Tone.js.map"],
    # Do developerki:
    "qunit": ["qunit/qunit.js", "qunit/qunit.css"],
    "sinon": ["pkg/sinon.js"],
}

REST_FRAMEWORK = {
    # Use Django's standard `django.contrib.auth` permissions,
    # or allow read-only access for unauthenticated users.
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.DjangoModelPermissionsOrAnonReadOnly"
    ],
    # Własna podklasa LimitOffsetPagination z twardym ``max_limit`` — patrz
    # api_v1.pagination (goły LimitOffsetPagination nie ma żadnego cap-a).
    "DEFAULT_PAGINATION_CLASS": "api_v1.pagination.BppLimitOffsetPagination",
    "PAGE_SIZE": 10,
    "DEFAULT_FILTER_BACKENDS": ["django_filters.rest_framework.DjangoFilterBackend"],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "oauth_mcp.authentication.StrictOAuth2Authentication",
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    # Globalny throttling pozostaje WYŁĄCZONY (mpasternak, 6.06.2020) — brak
    # DEFAULT_THROTTLE_CLASSES, więc większość endpointów nie jest limitowana.
    # Limitujemy WYŁĄCZNIE kosztowne endpointy wyszukiwania (opt-in per-viewset
    # przez api_v1.throttling: /szukaj/ pełnotekstowe oraz /autor/ z filtrem
    # nazwisko__icontains). Rate'y (klucze == scope) dają rozdzielne progi
    # anon/user; pod DummyCache (dev/test) throttling jest no-op.
    "DEFAULT_THROTTLE_RATES": {
        "search_anon": "60/minute",
        "search_user": "240/minute",
    },
}

BPP_WALIDUJ_AFILIACJE_AUTOROW = (
    os.getenv("DJANGO_BPP_WALIDUJ_AFILIACJE_AUTOROW", "tak") == "tak"
)

# ASGI_APPLICATION = "django_bpp.routing.application"
ASGI_APPLICATION = "django_bpp.asgi.application"

# Channel-layer key prefix (get_channels_prefix imported at top). Production:
# "asgi" (channels_redis default). Under pytest-xdist: "asgi-test-<worker>" so
# colliding per-user group names cannot cross-talk between workers sharing one
# Redis. See django_bpp.channels_prefix and docs/CHANNELS_BROADCAST_FLAKE.md.
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [(REDIS_HOST, REDIS_PORT)],
            "prefix": get_channels_prefix(),
        },
    },
}

# django-liveops: długo-działające operacje (np. skan duplikatów źródeł) z
# live-progressem przez WebSocket + HTMX. RUNNER="celery" dispatchuje run()
# jako shared_task na tym samym workerze co reszta BPP (autodiscover). Live
# push wymaga Redis channel-layer (skonfigurowany wyżej). W testach RUNNER
# jest nadpisywany na "eager" (settings/test.py) — skan biegnie synchronicznie
# bez Redis/workera.
LIVEOPS = {
    "BASE_TEMPLATE": "base.html",
    "RUNNER": "celery",
    "THROTTLE_HZ": 10,
}

# Pozwól anonimowym użytkownikom łączyć się z WebSocketem notyfikacji
# (/asgi/notifications/) i subskrybować globalny kanał "__all__".
#
# django-channels-broadcast domyślnie (CHANNELS_BROADCAST_ENABLE_ANONYMOUS=False)
# odrzuca anonimów w NotificationsConsumer.connect() przez self.close() PRZED
# self.accept() — uvicorn zwraca wtedy HTTP 403 na handshake, a przeglądarka
# raportuje NS_ERROR_WEBSOCKET_CONNECTION_REFUSED. Stary lokalny src/notifications/
# consumer akceptował połączenie bezwarunkowo, więc po przepięciu na pakiet
# zewnętrzny (refactor f6e0fa6cf) anonimowy front przestał się łączyć. Ta flaga
# przywraca poprzednie zachowanie. Kanał "__all__" jest globalnym broadcastem —
# nie publikuj na nim danych wrażliwych.
CHANNELS_BROADCAST_ENABLE_ANONYMOUS = True

# Autoryzator subskrypcji kanałów-stron (?extraChannels=). Bez niego
# channels_broadcast używa domyślnego _deny_all, który ODRZUCA każdą
# subskrypcję extraChannels — a paski postępu operacji long_running
# (import POLON, absencje, raporty…) subskrybują właśnie tak
# (extraChannels=[operation.pk]). Skutkiem braku było: dane importują się,
# ale pasek postępu stoi i strona nie przekierowuje po zakończeniu —
# użytkownik musiał ręcznie odświeżać. Autoryzator przepuszcza kanał-stronę
# operacji wyłącznie jej właścicielowi. Kanały liveop.* jadą tokenem
# (subscription_token) i omijają ten autoryzator.
CHANNELS_BROADCAST_SUBSCRIPTION_AUTHORIZER = (
    "long_running.authorizers.authorize_operation_channel"
)


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
            "rozbieznosci",
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
            "channels_broadcast",
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
DBTEMPLATES_USE_REVERSION_COMPARE = True

# Nasza tabela django_template ma kilka wierszy (override'y frontendu), a admin
# rozwiazuje ~150 szablonow na strone. Bez tej flagi dbtemplates pytalby DB o
# kazda taka nazwe (pod DummyCache w dev = ~300 zapytan/strone). Loader trzyma
# w procesie zbior istniejacych nazw i omija DB dla reszty. Patrz
# django-dbtemplates-iplweb >= 4.4.0 (DBTEMPLATES_SKIP_UNKNOWN_NAMES).
DBTEMPLATES_SKIP_UNKNOWN_NAMES = True

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
        ) from e
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
                `django_microsoft_auth`. Wyjątek przy próbie importu: {e}"""
            )
        ) from e
    MICROSOFT_AUTH_CLIENT_SECRET = env("MICROSOFT_AUTH_CLIENT_SECRET")
    MICROSOFT_AUTH_TENANT_ID = env("MICROSOFT_AUTH_TENANT_ID")
    MICROSOFT_AUTH_LOGIN_TYPE = "ma"
    MICROSOFT_AUTH_EXTRA_SCOPES = env("MICROSOFT_AUTH_EXTRA_SCOPES")

    # Zgodnie z dokumentacją z https://django-microsoft-auth.readthedocs.io/en/latest/usage.html,
    # wstaw microsoft_auth po contrib_sites.
    contrib_sites_index = INSTALLED_APPS.index("django.contrib.sites")
    INSTALLED_APPS = (
        INSTALLED_APPS[: contrib_sites_index + 1]
        + ["microsoft_auth"]
        + INSTALLED_APPS[contrib_sites_index + 1 :]
    )

    # Context processor removed - using MicrosoftAuthRedirect view instead
    # to avoid unnecessary network traffic on every page load

    AUTHENTICATION_BACKENDS = [
        "microsoft_auth.backends.MicrosoftAuthenticationBackend",
        "django.contrib.auth.backends.ModelBackend",
    ]

    # Konfiguracja w urls.py doda microsoft_auth.urls do ścieżki jezeli wykryje
    # aplikację `microsoft_auth` w INSTALLED_APPS

    # password_policies pozostaje aktywne -- ConditionalPasswordChangeMiddleware
    # rozróżnia OAuth (Microsoft, ORCID) od logowania klasycznego i pomija
    # egzekwowanie polityki haseł dla użytkowników zalogowanych zewnętrznie.

# Konfiguracja logout redirect dla Microsoft Auth
# To jest URL, na który użytkownik zostanie przekierowany po wylogowaniu z Microsoft
# Musi być zarejestrowany w aplikacji Azure AD jako Reply URL
MICROSOFT_AUTH_LOGOUT_REDIRECT_URL = "/"

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
# ORCID authentication backend — always available, enabled per-Uczelnia
#
if "AUTHENTICATION_BACKENDS" not in dir():
    AUTHENTICATION_BACKENDS = [
        "django.contrib.auth.backends.ModelBackend",
    ]
AUTHENTICATION_BACKENDS = list(AUTHENTICATION_BACKENDS) + [
    "orcid_integration.backends.OrcidAuthenticationBackend",
]

#
# Konfiguracja logowania OpenID Connect (Keycloak) — opcjonalna i ADDYTYWNA.
#
# Aktywuje się TYLKO gdy w środowisku jest komplet DJANGO_BPP_OIDC_*_{CLIENT_ID,
# CLIENT_SECRET,ISSUER} (z prefiksem skrótu uczelni lub bez). Nie przejmuje
# strony logowania — dokłada się jako kolejna metoda obok hasła/Microsoft/ORCID.
# Backend jest DOPISYWANY do listy (ModelBackend zostaje → logowanie hasłem
# działa równolegle).
#
from oidc_integration.conf import (  # noqa: E402
    discover_oidc_config,
    fetch_well_known_endpoints,
)

_OIDC_CONFIG = discover_oidc_config()
OIDC_LOGIN_ENABLED = _OIDC_CONFIG is not None
OIDC_LOGIN_SKROT = (_OIDC_CONFIG or {}).get("skrot") or ""

# App zawsze zainstalowany — model/tabela OIDCIdentity muszą istnieć
# niezależnie od env (routing i backend zostają warunkowe po _OIDC_CONFIG).
if "oidc_integration" not in INSTALLED_APPS:
    INSTALLED_APPS = list(INSTALLED_APPS) + ["oidc_integration"]

# Defaulty bezpieczne również dla instalacji bez OIDC.
OIDC_REQUIRE_EMAIL_VERIFIED = (_OIDC_CONFIG or {}).get("require_email_verified", True)
OIDC_GRACE_BIND_ENABLED = (_OIDC_CONFIG or {}).get("grace_bind", False)

if _OIDC_CONFIG:
    OIDC_OP_ISSUER = _OIDC_CONFIG["issuer"]

    OIDC_RP_CLIENT_ID = _OIDC_CONFIG["client_id"]
    OIDC_RP_CLIENT_SECRET = _OIDC_CONFIG["client_secret"]

    # Źródła claimów (konfigurowalne env-em, default mail-first / username z
    # preferred_username) — czytane przez BppOIDCBackend.
    OIDC_EMAIL_CLAIMS = _OIDC_CONFIG["email_claims"]
    OIDC_USERNAME_CLAIMS = _OIDC_CONFIG["username_claims"]

    # Endpointy: preferuj .well-known (źródło prawdy serwera), z fallbackiem na
    # konwencję Keycloaka gdy IdP nieosiągalny przy starcie.
    _oidc_endpoints = (
        fetch_well_known_endpoints(_OIDC_CONFIG["issuer"]) or _OIDC_CONFIG["endpoints"]
    )
    OIDC_OP_AUTHORIZATION_ENDPOINT = _oidc_endpoints["authorization"]
    OIDC_OP_TOKEN_ENDPOINT = _oidc_endpoints["token"]
    OIDC_OP_USER_ENDPOINT = _oidc_endpoints.get("userinfo", "")
    OIDC_OP_JWKS_ENDPOINT = _oidc_endpoints["jwks"]
    # end_session: wylogowanie z Keycloaka (RP-Initiated Logout).
    OIDC_OP_LOGOUT_ENDPOINT = _oidc_endpoints.get("end_session", "")
    OIDC_OP_LOGOUT_URL_METHOD = "oidc_integration.logout.build_provider_logout_url"

    # Panel konta Keycloaka (Account Console) — konwencja {issuer}/account.
    # Tam użytkownik OIDC zmienia hasło; w BPP nie ma takiej możliwości, więc
    # SmartPasswordChangeView kieruje go pod ten URL zamiast formularza BPP.
    OIDC_ACCOUNT_CONSOLE_URL = _OIDC_CONFIG["issuer"].rstrip("/") + "/account"

    # Keycloak podpisuje id_token RS256; scope email konieczny do auto-create.
    OIDC_RP_SIGN_ALGO = "RS256"
    OIDC_RP_SCOPES = "openid email profile"
    OIDC_CREATE_USER = True
    # Zapamiętaj id_token w sesji — potrzebny jako id_token_hint przy logout.
    OIDC_STORE_ID_TOKEN = True

    AUTHENTICATION_BACKENDS = list(AUTHENTICATION_BACKENDS) + [
        "oidc_integration.backends.BppOIDCBackend",
    ]

#
# Koniec konfiguracji OpenID Connect
#

#
# django-axes — ochrona przed zgadywaniem hasła (brute-force / credential stuffing)
#
# AxesStandaloneBackend NIE uwierzytelnia sam — tylko sprawdza, czy dana próba
# nie jest już zablokowana, i musi stać PIERWSZY na liście, żeby zawetować
# zablokowane logowanie zanim trafi ono do LDAP / Microsoft / ORCID / Model.
# (Używamy "Standalone", bo własne backendy zostają — w przeciwieństwie do
# AxesBackend, który zastąpiłby uwierzytelnianie ModelBackendem.)
AUTHENTICATION_BACKENDS = [
    "axes.backends.AxesStandaloneBackend",
] + list(AUTHENTICATION_BACKENDS)

# Polityka lockoutu (PCI-DSS 8.3.4: ≤10 prób, blokada ≥30 min):
AXES_FAILURE_LIMIT = 10  # 10 nieudanych prób...
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]  # ...na parę (login, IP)
AXES_COOLOFF_TIME = timedelta(minutes=30)  # auto-odblokowanie po 30 min
AXES_RESET_ON_SUCCESS = True  # udane logowanie zeruje licznik nieudanych prób
AXES_ENABLE_ADMIN = True  # podgląd/odblokowanie prób z panelu admina
# IP klienta zza nginx: bierzemy OSTATNI wpis X-Forwarded-For (doklejony przez
# nginx z $remote_addr = realny klient, niefalsyfikowalny). Bez tego axes użyłby
# REMOTE_ADDR = IP nginxa i komponent (ip_address) lockoutu zlałby się do jednej
# wartości dla wszystkich. Patrz django_bpp/client_ip.py.
AXES_CLIENT_IP_CALLABLE = "django_bpp.client_ip.get_client_ip"
# Handler bazodanowy (domyślny) działa jednolicie w dev/test/prod; cache handler
# byłby no-op pod DummyCache (dev/test). Tabela AccessAttempt daje wgląd w adminie.
#
# Blokujemy po KOMBINACJI (login + IP), nie po samym loginie — twardy lockout
# konta jest wektorem DoS (atakujący celowo blokuje ofiarę złym hasłem; NIST
# SP 800-63B przed tym ostrzega). Atakującemu z jednego IP wystarczy ~10 prób/30
# min na konto — grubo poniżej pułapu NIST (100/h), a ofiara nie traci dostępu
# globalnie.
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
DJANGO_EASY_AUDIT_PROPAGATE_EXCEPTIONS = True

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

# NOTE: BPP used to override ``dynamic_admin_columns`` migrations via
# ``MIGRATION_MODULES`` because the package's old ``0001_initial`` ran a
# plain ``CreateModel`` that collided with the ``dynamic_columns_*``
# tables every BPP database already carries (legacy in-tree app +
# baseline-loaded test DBs). Since django-dynamic-admin-columns 0.5.0
# that migration is idempotent (creates the tables only when absent,
# via the schema editor so the user FK resolves through
# ``AUTH_USER_MODEL``), so the override is no longer needed and BPP
# consumes the package's migrations directly. Schema-level work for the
# legacy per-user upgrade still lives in
# ``bpp.0416_rename_dynamic_columns_to_admin``.

DYNAMIC_ADMIN_COLUMNS_ALLOWED_IMPORT_PATHS = [
    "bpp.admin.wydawnictwo_ciagle",
    "bpp.admin.wydawnictwo_zwarte",
    "bpp.admin.autor",
]

DYNAMIC_ADMIN_COLUMNS_FORBIDDEN_COLUMN_NAMES = [
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
    "promotion": False,
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
# W trybie multi-hosted można wyłączyć sitemaps ustawiając
# DJANGO_BPP_ENABLE_SITEMAPS=False, ponieważ static-sitemaps
# generuje sitemapę tylko dla jednej domeny (SITE_ID).
#

ENABLE_SITEMAPS = env("DJANGO_BPP_ENABLE_SITEMAPS", default=True, cast=bool)

if ENABLE_SITEMAPS:
    STATICSITEMAPS_ROOT_SITEMAP = "django_bpp.sitemaps.django_bpp_sitemaps"
    STATICSITEMAPS_REFRESH_AFTER = 24 * 60
    STATICSITEMAPS_ROOT_DIR = os.path.relpath(STATIC_ROOT, os.getcwd())
else:
    if "static_sitemaps" in INSTALLED_APPS:
        INSTALLED_APPS.remove("static_sitemaps")

#
# "Audyt" bezpieczeństwa
#

CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = True

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = True

LANGUAGE_COOKIE_SECURE = True

X_FRAME_OPTIONS = "SAMEORIGIN"

DATA_UPLOAD_MAX_NUMBER_FIELDS = 5000

# Twardy, parse-time limit liczby plików na jedno żądanie (Django default to
# 100). Jedyny formularz w BPP przyjmujący wiele plików naraz to kreator
# zgłaszania publikacji (MultipleFileField, max 5 plików); reszta wgrywa
# pojedyncze pliki. Ustawiamy 10 (margines nad 5) — Django odrzuca nadmiar
# już przy parsowaniu multiparta, zanim pliki wylądują w /tmp, ograniczając
# anonimowy DoS przez masowe uploady. Twardy cap na bajty daje nginx
# (client_max_body_size).
DATA_UPLOAD_MAX_NUMBER_FILES = 10

# django-formdefaults: pozwól wszystkim staff-userom edytować systemowe
# wartości domyślne formularzy (domyślnie pakiet wpuszcza tylko superuserów).
FORMDEFAULTS_CAN_EDIT_SYSTEM_WIDE = "bpp.formdefaults_perms.can_edit_system_wide"

DJANGO_BPP_SKROT_WYDZIALU_W_NAZWIE_JEDNOSTKI = env(
    "DJANGO_BPP_SKROT_WYDZIALU_W_NAZWIE_JEDNOSTKI"
)

# polish-inflection: słowo spoza słownika SGJP → passthrough (nie błąd renderu)
POLISH_INFLECTION_STRICT = False

#
# Po zalogowaniu się do PBN ustalamy, że token jest ważny [TYLE] godzin
#

PBN_TOKEN_HOURS_GRACE_TIME = 24

#
# Ograniczanie eksportu z Admina
#

BPP_MAX_ALLOWED_EXPORT_ITEMS = env("DJANGO_BPP_MAX_ALLOWED_EXPORT_ITEMS")

#
# Pagination configuration for dj_pagination
#
# This controls how many page numbers are shown around the current page
# With WINDOW=2, it shows: first ... [current-2] [current-1] current [current+1] [current+2] ... last
# This results in maximum 8 elements in the pagination
PAGINATION_DEFAULT_WINDOW = 2
PAGINATION_DEFAULT_MARGIN = 1

#
#
#

DJANGO_BPP_ENABLE_TEST_CONFIGURATION = env("DJANGO_BPP_ENABLE_TEST_CONFIGURATION")
# DJANGO_BPP_ENABLE_TEST_CONFIGURATION = True


#
# ROLLBAR settings
#

# pyrollbar dopasowuje pola do scrubu po DOKŁADNEJ nazwie klucza (case-insensitive,
# NIE po sufiksie) i PODMIENIA swoją domyślną listę, gdy podamy własną. Dlatego
# odtwarzamy tu domyślny zestaw pyrollbara i DOKŁADAMY sekrety OAuth/MCP i PBN
# (uwaga reviewera #3/#5): DOT oznacza jako wrażliwe tylko password/client_secret,
# a Rollbar bez tej listy wysłałby aktywny refresh_token / code / code_verifier /
# token przy nieoczekiwanym 500 na /o/token/ czy /o/revoke_token/.
ROLLBAR_SCRUB_FIELDS = [
    # domyślne pyrollbara (zachowujemy — nasza lista je nadpisuje):
    "pw",
    "passwd",
    "password",
    "secret",
    "confirm_password",
    "confirmPassword",
    "password_confirmation",
    "passwordConfirmation",
    "access_token",
    "accessToken",
    "auth",
    "authentication",
    "authorization",
    # sekrety OAuth/MCP (dokładne nazwy pól — exact match):
    "token",
    "refresh_token",
    "refreshToken",
    "code",
    "code_verifier",
    "codeVerifier",
    "client_secret",
    "clientSecret",
    "secret_key",
    "api_key",
    # sekrety PBN / nagłówki uwierzytelniające (defense-in-depth, #4/#5):
    "user_token",
    "app_token",
    "x-user-token",
    "x-app-token",
    "cookie",
    "set-cookie",
]

ROLLBAR = {
    "access_token": env("ROLLBAR_ACCESS_TOKEN"),
    "environment": "development",
    "code_version": VERSION,
    "root": BASE_DIR,
    "scrub_fields": ROLLBAR_SCRUB_FIELDS,
    "ignorable_404_urls": (
        re.compile(r"/favicon\.ico"),
        re.compile(r".*\{\{\s*clickURL\s*\}\}$"),
    ),
}

# Publiczny token klienta (post_client_item) do frontendowego Rollbara.
# INNY niż sekretny ROLLBAR["access_token"] (post_server_item) — ten można
# bezpiecznie renderować w przeglądarce. Pusty = front-end Rollbar wyłączony.
ROLLBAR_CLIENT_ACCESS_TOKEN = env("ROLLBAR_CLIENT_ACCESS_TOKEN")

#
# Prometheus
#

DJANGO_BPP_ENABLE_PROMETHEUS = env("DJANGO_BPP_ENABLE_PROMETHEUS")

if DJANGO_BPP_ENABLE_PROMETHEUS:
    MIDDLEWARE = (
        [
            "django_prometheus.middleware.PrometheusBeforeMiddleware",
        ]
        + MIDDLEWARE
        + [
            "django_prometheus.middleware.PrometheusAfterMiddleware",
        ]
    )

    INSTALLED_APPS += [
        "django_prometheus",
    ]

DYNAMIC_FILTER_COUNTS_ENABLE = env("DYNAMIC_FILTER_COUNTS_ENABLE")

# =============================================================================
# LOGGING CONFIGURATION
# =============================================================================

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        # Format z timestampem - dla wszystkiego co nie pochodzi z pbn_import.
        # Korelacja logów między workerami w produkcji wymaga timestampu w
        # samym logu, nie tylko z systemd/celery (które dorzuca swój dopiero
        # przy stdout, ale nie do plików ani Rollbara).
        "default": {
            "format": ("[%(asctime)s] [%(levelname)s] %(name)s: %(message)s"),
            "datefmt": "%Y-%m-%d %H:%M:%S",
        },
        "pbn_import": {
            # Format użytkownika końcowego — bez timestampu, bo pbn_import
            # piszący do konsoli przy interaktywnym imporcie ma być czytelny.
            "format": "[%(levelname)s] %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
            "formatter": "default",
        },
        "pbn_import_console": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
            "formatter": "pbn_import",
        },
    },
    "loggers": {
        # Eventy bezpieczeństwa Django (DisallowedHost, SuspiciousOperation,
        # bad CSRF token, etc.) - widoczne na WARNING+
        "django.security": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        # 4xx i 5xx z requests - WARNING bo INFO byłby spamem.
        "django.request": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        # Celery workery - retry, ack, errors. INFO to dobry kompromis.
        "celery": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        # pbn_import - format bez timestampu (UI-style)
        "pbn_import": {
            "handlers": ["pbn_import_console"],
            "level": "INFO",
            "propagate": False,
        },
        # Logger dla pbn_api - WARNING+ na konsolę. W szczególności
        # `_check_error_response` w transport.py loguje pełne body
        # i headers przy odpowiedziach >= 400, co jest kluczowe przy
        # diagnostyce błędów typu „400 Bad Request" bez czytelnego body.
        "pbn_api": {
            "handlers": ["console"],
            "level": "WARNING",
            "propagate": False,
        },
        # OIDC (Keycloak). Domyślnie WARNING — zwykła praca milczy. Diagnostyka
        # claimów realmu (`_log_claims_debug` w backends.py zrzuca KAŻDY klucz
        # i wartość) wymaga opt-in: ustaw DJANGO_BPP_OIDC_DEBUG_CLAIMS=1 i zaloguj
        # się przez Keycloaka, żeby zobaczyć faktyczne nazwy claimów na stderr.
        # ⚠️ DEBUG loguje też wartości (adresy e-mail, login) — włączaj tylko
        # do diagnostyki, nie zostawiaj na produkcji.
        "oidc_integration": {
            "handlers": ["console"],
            "level": (
                "DEBUG"
                if os.getenv("DJANGO_BPP_OIDC_DEBUG_CLAIMS") == "1"
                else "WARNING"
            ),
            # propagate=True (inaczej niż sąsiednie loggery): root nie ma tu
            # własnego handlera, więc propagacja nie dubluje wyjścia, a pozwala
            # pytestowemu `caplog` (łapie na rootcie) widzieć zrzut claimów.
            "propagate": True,
        },
    },
}

#
# Cacheops nawet na staging serwerze wymaga tych ustawień, bo potrafi łączyć
# się z redisem nawet, gdy generalna konfiguracja jest nie ustawiona
#

CACHEOPS_REDIS = {
    "host": REDIS_HOST,  # redis-server is on same machine
    "port": REDIS_PORT,  # default redis port
    "db": env("DJANGO_BPP_REDIS_DB_CACHEOPS"),
    # 'socket_timeout': 3,   # connection timeout in seconds, optional
    # 'password': '...',     # optional
    # 'unix_socket_path': '' # replaces host and port
}

#
# Django-Constance - dynamiczne ustawienia techniczne
#
CONSTANCE_BACKEND = "constance.backends.database.DatabaseBackend"
CONSTANCE_DATABASE_CACHE_BACKEND = "constance_cache"

# Ustawienia per-uczelnia przeniesione do modelu Uczelnia:
# UZYWAJ_PUNKTACJI_WEWNETRZNEJ, POKAZUJ_INDEX_COPERNICUS, POKAZUJ_PUNKTACJA_SNIP,
# POKAZUJ_OSWIADCZENIE_KEN, SKROT_WYDZIALU_W_NAZWIE_JEDNOSTKI,
# UCZELNIA_UZYWA_WYDZIALOW, GOOGLE_ANALYTICS_PROPERTY_ID,
# GOOGLE_VERIFICATION_CODE, WYDRUK_MARGINES_*
# Puste CONSTANCE_CONFIG zachowane dla backward compat z django-constance.
CONSTANCE_CONFIG = {}
CONSTANCE_CONFIG_FIELDSETS = {}

#
# django-oauth-toolkit (DOT) — Authorization Server dla serwera MCP (`/o/`).
# NIE dodawaj `ALLOWED_GRANT_TYPES` — taki klucz nie istnieje w DOT i
# zostałby po cichu zignorowany. Granty kontroluje DCR (Task 6/7) i atrybut
# `Application.authorization_grant_type`.
#
OAUTH2_PROVIDER = {
    "PKCE_REQUIRED": True,
    "DEFAULT_SCOPES": ["read"],
    "SCOPES": {"read": "Odczyt danych BPP w Twoim imieniu"},
    "ROTATE_REFRESH_TOKEN": True,
    "ACCESS_TOKEN_EXPIRE_SECONDS": 60 * 30,  # 30 min
    "REFRESH_TOKEN_EXPIRE_SECONDS": 60 * 60 * 24 * 7,  # 7 dni (NIE None!)
}
