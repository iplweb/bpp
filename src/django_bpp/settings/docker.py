"""
Docker development settings.

Inherits from local.py but uses Redis for sessions to enable
session sharing between appserver and authserver containers.
"""

from .local import *  # noqa
from .local import REDIS_HOST, REDIS_PORT, env

# Use cache-based sessions (same as production/authserver)
SESSION_ENGINE = "django.contrib.sessions.backends.cache"

# Use Redis for default cache instead of DummyCache
# This enables session sharing with authserver
CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:{REDIS_PORT}",
        "OPTIONS": {
            "DB": env("DJANGO_BPP_REDIS_DB_CACHE"),
            "CONNECTION_POOL_CLASS": "redis.BlockingConnectionPool",
            "CONNECTION_POOL_CLASS_KWARGS": {
                "max_connections": 50,
                "timeout": 20,
            },
        },
    },
    "constance_cache": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": f"redis://{REDIS_HOST}:{REDIS_PORT}/8",
        "OPTIONS": {
            "CONNECTION_POOL_CLASS": "redis.BlockingConnectionPool",
            "CONNECTION_POOL_CLASS_KWARGS": {
                "max_connections": 50,
                "timeout": 20,
            },
        },
    },
}
