from .base import *  # noqa

DEBUG = False
DEBUG_TOOLBAR = False
SENDFILE_BACKEND = "sendfile.backends.nginx"

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

COMPRESS_ENABLED = not DEBUG
COMPRESS_OFFLINE = False

HTML_MINIFY = True

SESSION_ENGINE = "django.contrib.sessions.backends.cache"

CACHES = {
    "default": {
        "BACKEND": "redis_cache.RedisCache",
        "LOCATION": [
            f"{REDIS_HOST}:{REDIS_PORT}",  # noqa
        ],
        "OPTIONS": {
            "DB": env("DJANGO_BPP_REDIS_DB_CACHE"),  # noqa
            "PARSER_CLASS": "redis.connection.HiredisParser",
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

DATABASES["default"]["CONN_MAX_AGE"] = None  # noqa

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

EMAIL_BACKEND = "djcelery_email.backends.CeleryEmailBackend"

# django-easy-audit

INSTALLED_APPS.append("easyaudit")  # noqa
MIDDLEWARE.append(  # noqa
    "easyaudit.middleware.easyaudit.EasyAuditMiddleware",
)

# djcelery_email
INSTALLED_APPS.append("djcelery_email")  # noqa
