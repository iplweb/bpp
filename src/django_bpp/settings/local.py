# Lokalny development (na moim Maku)

import os
import sys


def setenv_default(varname, default_value):
    if os.environ.get(varname) is None:
        os.environ[varname] = default_value


setenv_default("DJANGO_SETTINGS_MODULE", "django_bpp.settings.local")
setenv_default("DJANGO_BPP_SECRET_KEY", "0xdeadbeef 2")

from .base import *  # noqa
from .base import (  # noqa
    DATABASES,
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
    "mac.iplweb",
    "publikacje-test",
    "test.unexistenttld",
    env("DJANGO_BPP_HOSTNAME"),  # noqa
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
    "dbtemplates.loader.Loader",
    "django.template.loaders.filesystem.Loader",
    "django.template.loaders.app_directories.Loader",
]

# Disable setup wizard middleware during tests

if "pytest" in sys.modules:
    MIDDLEWARE = [
        m
        for m in MIDDLEWARE
        if m != "bpp_setup_wizard.middleware.SetupWizardMiddleware"
    ]
    # Testy nie powinny korzystać z cacheops — paczka monkey-patchuje
    # globalnie Manager.get / QuerySet.* i potrafi wywalać
    # NotSupportedError / ForeignKeyViolation przy losowej kolejności
    # xdist workerów (queryset-y dzielą stan `combinator` między
    # testami). Usunięcie cacheops z INSTALLED_APPS w trybie pytest
    # wyłącza monkey-patching — produkcja dalej używa cacheops
    # z pełnym CACHEOPS dict w production.py.
    INSTALLED_APPS = [app for app in INSTALLED_APPS if app != "cacheops"]
    # Sam INSTALLED_APPS-prune NIE wystarczy: dekorator @cached
    # (cacheops.simple) jest niezależny od `cacheops` w INSTALLED_APPS,
    # nadal pisze/czyta z Redis db=7. Pod xdist Redis jest jeden na
    # sesję pytest, więc workery widzą nawzajem swoje cache'owane wyniki
    # — np. `get_uczelnia_context_data` cache'uje `recently_updated`
    # z PK-ami publikacji workera A, worker B renderuje homepage z tymi
    # linkami i potem dostaje 404 na `/bpp/rekord/<ct>,<pk>/`.
    # Wyłączenie CACHEOPS_ENABLED zamienia `@cached` w no-op
    # (cacheops/simple.py:54) i propaguje się też na `invalidate_*`,
    # które same sprawdzają tę flagę.
    CACHEOPS_ENABLED = False


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
