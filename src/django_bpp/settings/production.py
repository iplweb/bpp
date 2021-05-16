# -*- encoding: utf-8 -*-

from .base import *  # noqa

DEBUG = False
DEBUG_TOOLBAR = False
SENDFILE_BACKEND = "sendfile.backends.nginx"

SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False

COMPRESS_ENABLED = not DEBUG
COMPRESS_OFFLINE = False

TEMPLATES[0]["OPTIONS"]["loaders"] = [  # noqa
    (
        "django.template.loaders.cached.Loader",
        TEMPLATES[0]["OPTIONS"]["loaders"],  # noqa
    )
]

HTML_MINIFY = True

SESSION_ENGINE = "django.contrib.sessions.backends.cache"

CACHES = {
    "default": {
        "BACKEND": "redis_cache.RedisCache",
        "LOCATION": [
            f"{REDIS_HOST}:{REDIS_PORT}",  # noqa
        ],
        "OPTIONS": {
            "DB": REDIS_DB_CACHE,  # noqa
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
