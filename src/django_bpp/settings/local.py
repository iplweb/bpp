# Lokalny development (na moim Maku).
#
# Czysto deweloperska konfiguracja (runserver, shell, dev celery). Testy
# NIE używają tego pliku bezpośrednio — jadą na ``django_bpp.settings.test``
# (patrz ``pytest.ini`` --ds), który dziedziczy stąd przez ``from .local
# import *`` i dokłada modyfikacje specyficzne dla pytest.

import os


def setenv_default(varname, default_value):
    if os.environ.get(varname) is None:
        os.environ[varname] = default_value


setenv_default("DJANGO_SETTINGS_MODULE", "django_bpp.settings.local")
setenv_default("DJANGO_BPP_SECRET_KEY", "0xdeadbeef 2")
# Staly dev-owy klucz Fernet dla EncryptedTextField (credentiale DSpace itd.).
# Bez niego zapis pola EncryptedTextField wywala ImproperlyConfigured
# (src/bpp/fields.py). Stala wartosc (nie generowana co restart), zeby
# rekordy zaszyfrowane wczesniej dalo sie odszyfrowac po restarcie. Dev-only:
# local.py nie laduje sie w produkcji — tam klucz przychodzi z prawdziwego
# env/.env. Override: ustaw DSPACE_CREDENTIALS_KEY w srodowisku przed startem.
setenv_default("DSPACE_CREDENTIALS_KEY", "beRCn4RUNneKiOizMZEEZDjeZVwdOJ6m2etsvwC3wfs=")

from .base import *  # noqa
from .base import (  # noqa
    DATABASES,
    DJANGO_BPP_HOSTNAMES,
    INSTALLED_APPS,
    MIDDLEWARE,
    REDIS_HOST,
    REDIS_PORT,
    TEMPLATES,
    env,
)

# DEBUG = False
DEBUG = True

SENDFILE_BACKEND = "django_sendfile.backends.simple"

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

MEDIA_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), "..", "..", "media")
)
SENDFILE_ROOT = MEDIA_ROOT

COMPRESS_ENABLED = False  # not DEBUG
COMPRESS_OFFLINE = False

ALLOWED_HOSTS = [
    "dockerhost",
    "localhost",
    "127.0.0.1",
    "mac-mini",
    "publikacje-test",
    "test.unexistenttld",
    *DJANGO_BPP_HOSTNAMES,
]

CELERY_ALWAYS_EAGER = False
# CELERY_ALWAYS_EAGER = True
CELERY_EAGER_PROPAGATES_EXCEPTIONS = True

PUNKTUJ_MONOGRAFIE = False

DEBUG_TOOLBAR = False
# DEBUG_TOOLBAR = True

if DEBUG_TOOLBAR and DEBUG:
    MIDDLEWARE = [
        "debug_toolbar.middleware.DebugToolbarMiddleware",
        "bpp.middleware.NonHtmlDebugToolbarMiddleware",
    ] + MIDDLEWARE

    INSTALLED_APPS.append("debug_toolbar")

DATABASES["default"]["CONN_MAX_AGE"] = 0


# Vide komentarz w TEMPLATES[0]["OPTIONS"]["loaders"]
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.dummy.DummyCache",
    },
    "constance_cache": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:{REDIS_PORT}/8",  # DB 8 for constance
        "OPTIONS": {
            "CONNECTION_POOL_CLASS": "redis.BlockingConnectionPool",
            "CONNECTION_POOL_CLASS_KWARGS": {
                "max_connections": 50,
                "timeout": 20,
            },
        },
    },
}


TEMPLATES[0]["OPTIONS"]["loaders"] = [  # noqa
    "admin_tools.template_loaders.Loader",
    # DBTEMPLATES_SKIP_UNKNOWN_NAMES (base.py) sprawia, ze ten loader nie pyta
    # DB o nazwy spoza tabeli — krytyczne w dev, gdzie CACHES["default"] to
    # DummyCache (nizej) i negatywne lookupy nie byly cache'owane.
    "dbtemplates.loader.Loader",
    "django.template.loaders.filesystem.Loader",
    "django.template.loaders.app_directories.Loader",
]

# django-easy-audit

INSTALLED_APPS.append("easyaudit")  # noqa
MIDDLEWARE.append(  # noqa
    "easyaudit.middleware.easyaudit.EasyAuditMiddleware",
)


# django-dev-helpers — autologin endpoint + dotfiles dla agentow LLM.
# Aktywuje sie samo, gdy run-site uruchamia stack i ustawia
# DJANGO_DEV_HELPERS_ENABLED=1 (poza tym AppConfig.ready() jest no-op).
# Trzymamy w `local.py` zamiast `base.py`, zeby produkcja nie musiala
# instalowac dev-only dependency. Patrz pyproject.toml > [optional].dev.
try:
    import django_dev_helpers  # noqa: F401

    INSTALLED_APPS.append("django_dev_helpers")
except ImportError:
    # Dev-deps nie zainstalowane (np. ktos uruchamia local.py w obrazie
    # produkcyjnym dla testow rece). Pomijamy bez bledu — autologin
    # i tak by sie nie wlaczyl bez DJANGO_DEV_HELPERS_ENABLED=1.
    pass
