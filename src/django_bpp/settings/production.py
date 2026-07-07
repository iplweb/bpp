from django_minify_html.middleware import MinifyHtmlMiddleware

from .base import *  # noqa
from .base import (  # noqa
    DJANGO_BPP_ENABLE_TEST_CONFIGURATION,
    DJANGO_BPP_HOSTNAMES,
    INSTALLED_APPS,
    MIDDLEWARE,
    REDIS_HOST,
    REDIS_PORT,
    ROLLBAR,
    env,
)

DEBUG = False
DEBUG_TOOLBAR = False
SENDFILE_BACKEND = "django_sendfile.backends.nginx"

COMPRESS_ENABLED = not DEBUG
COMPRESS_OFFLINE = False


class BppMinifyHtmlMiddleware(MinifyHtmlMiddleware):
    # keep_input_type_text_attr: Foundation 6 stylizuje <input> selektorem
    # input[type="text"]; bez atrybutu (minifier usuwa go jako domyślny
    # per HTML5) selektor się nie dopasowuje i pole traci styling.
    # keep_closing_tags: treści z BD (np. <jats:p> w abstraktach) po zrzuceniu
    # opcjonalnych </li>, </p> łamią DOM i rozbijają layout (m.in. stopkę).
    minify_args = {
        "minify_css": True,
        "minify_js": True,
        "keep_input_type_text_attr": True,
        "keep_closing_tags": True,
    }

    def should_minify(self, request, response):
        # HTMX swap-uje fragmenty przez hx-swap="innerHTML"; minify-html jest
        # zaprojektowane do pełnych dokumentów (z <html>/<body>) i na samych
        # fragmentach potrafi rozjechać strukturę DOM (m.in. usuwa puste
        # elementy, restrukturyzuje listy). Skutek: stopka strony lądowała
        # między pagerem a tabelą po htmx-owym refreshu /pbn_export_queue.
        if request.headers.get("HX-Request") == "true":
            return False
        return super().should_minify(request, response)


MIDDLEWARE = [
    "django_bpp.settings.production.BppMinifyHtmlMiddleware",
] + MIDDLEWARE

SESSION_ENGINE = "django.contrib.sessions.backends.cache"

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": [
            f"redis://{REDIS_HOST}:{REDIS_PORT}",  # noqa
        ],
        "OPTIONS": {
            "DB": env("DJANGO_BPP_REDIS_DB_CACHE"),  # noqa
            "CONNECTION_POOL_CLASS": "redis.BlockingConnectionPool",
            #
            "CONNECTION_POOL_CLASS_KWARGS": {
                "max_connections": 50,
                "timeout": 20,
            },
            "MAX_CONNECTIONS": 1000,
            "PICKLE_VERSION": -1,
        },
    },
    "constance_cache": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": [
            f"redis://{REDIS_HOST}:{REDIS_PORT}/8",  # DB 8 for constance
        ],
        "OPTIONS": {
            "CONNECTION_POOL_CLASS": "redis.BlockingConnectionPool",
            "CONNECTION_POOL_CLASS_KWARGS": {
                "max_connections": 50,
                "timeout": 20,
            },
            "MAX_CONNECTIONS": 1000,
            "PICKLE_VERSION": -1,
        },
    },
}

CACHE_MIDDLEWARE_SECONDS = 3600 * 24

DATA_UPLOAD_MAX_MEMORY_SIZE = 2621440 * 3  # 7.5 MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 50000

CACHEOPS = {
    "bpp.bppmultiseekvisibility": {"ops": ("get", "fetch", "count", "exists")},
    "pbn_api.scientist": {"ops": ("get", "fetch", "count", "exists")},
    "pbn_api.journal": {"ops": ("get", "fetch", "count", "exists")},
    "pbn_api.publisher": {"ops": ("get", "fetch", "count", "exists")},
    "pbn_api.publication": {"ops": ("get", "fetch", "count", "exists")},
    "dbtemplates.template": {"ops": ("fetch", "get", "count", "exists")},
    "bpp.szablondlaopisubibliograficznego": {
        "ops": ("fetch", "get", "count", "exists")
    },
    "siteblog.article": {"ops": ("get", "fetch", "count", "exists")},
    "contenttypes.contenttype": {"ops": ("get", "fetch", "count", "exists")},
    "ewaluacja_common.rodzaj_autora": {"ops": ("fetch", "get", "count", "exists")},
    "bpp.rzeczownik": {"ops": ("fetch", "get", "count", "exists")},
    "django_countdown.SiteCountdown": {"ops": ("fetch", "get", "count", "exists")},
    "bpp.uczelnia": {"ops": ("get", "fetch", "count", "exists")},
    "bpp.jednostka": {"ops": ("get", "fetch", "count", "exists")},
    "bpp.wydawnictwo_ciagle_streszczenie": {"ops": ("get", "fetch", "count", "exists")},
}

CACHEOPS_DEFAULTS = {"timeout": 60 * 60}

ALLOWED_HOSTS = [
    "127.0.0.1",
    "appserver",
    "appserver:8000",
    *DJANGO_BPP_HOSTNAMES,
]

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")


if (
    ".console." not in EMAIL_BACKEND  # noqa
    and ".dummy." not in EMAIL_BACKEND  # noqa
    and ".locmem." not in EMAIL_BACKEND  # noqa
):
    # Użyj djcelery_email wyłacznie gdy ustawiony jest "prawdziwy" backend
    EMAIL_BACKEND = "djcelery_email.backends.CeleryEmailBackend"
    INSTALLED_APPS.append("djcelery_email")  # noqa

# django-easy-audit

INSTALLED_APPS.append("easyaudit")  # noqa
MIDDLEWARE.append(  # noqa
    "easyaudit.middleware.easyaudit.EasyAuditMiddleware",
)


ROLLBAR["environment"] = "production"  # noqa

if DJANGO_BPP_ENABLE_TEST_CONFIGURATION:  # noqa
    ROLLBAR["environment"] = "staging"  # noqa
