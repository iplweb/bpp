from .base import *  # noqa

DEBUG = False
DEBUG_TOOLBAR = False
SENDFILE_BACKEND = "django_sendfile.backends.nginx"

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

COMPRESS_ENABLED = not DEBUG
COMPRESS_OFFLINE = False

HTML_MINIFY = True

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
}

CACHE_MIDDLEWARE_SECONDS = 3600 * 24

DATA_UPLOAD_MAX_MEMORY_SIZE = 2621440 * 3  # 7.5 MB
DATA_UPLOAD_MAX_NUMBER_FIELDS = 50000

CACHEOPS = {
    "bpp.bppmultiseekvisibility": {"ops": ("get", "fetch")},
    "dbtemplates.template": {"ops": ("fetch", "get")},
    "bpp.szablondlaopisubibliograficznego": {"ops": ("fetch", "get")},
    "miniblog.article": {"ops": ("get", "fetch")},
    "contenttypes.contenttype": {"ops": ("get", "fetch")},
}
CACHEOPS_REDIS = BROKER_URL  # noqa
CACHEOPS_DEFAULTS = {"timeout": 60 * 60}

ALLOWED_HOSTS = [
    "127.0.0.1",
    env("DJANGO_BPP_HOSTNAME"),  # noqa
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
