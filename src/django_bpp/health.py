"""Health check endpoint and log filters for Docker healthcheck probes.

Used by both the main appserver and the lightweight authserver.
Returns 200 with `ok` if PostgreSQL is reachable (and Redis, when
``CELERY_BROKER_URL`` is configured), 503 with the failing component(s)
otherwise. The Redis probe is skipped on settings that do not configure
a broker (e.g. the lightweight authserver), since their healthiness does
not depend on it. Probe is bounded by short socket timeouts so a hung
backend does not hang the docker healthcheck.
"""

import logging

from django.conf import settings
from django.db import connection
from django.http import JsonResponse

logger = logging.getLogger(__name__)

_REDIS_TIMEOUT_SECONDS = 2


def _check_db():
    try:
        connection.ensure_connection()
        with connection.cursor() as cur:
            cur.execute("SELECT 1")
            cur.fetchone()
    except Exception as exc:
        logger.warning("healthcheck: db failed: %r", exc)
        return f"db: {exc.__class__.__name__}"
    return None


def _check_redis():
    broker_url = getattr(settings, "CELERY_BROKER_URL", None)
    if not broker_url:
        return None
    try:
        import redis

        client = redis.from_url(
            broker_url,
            socket_connect_timeout=_REDIS_TIMEOUT_SECONDS,
            socket_timeout=_REDIS_TIMEOUT_SECONDS,
        )
        client.ping()
    except Exception as exc:
        logger.warning("healthcheck: redis failed: %r", exc)
        return f"redis: {exc.__class__.__name__}"
    return None


def health_check(_request):
    """Health probe — pings DB and Redis, returns 503 if either is down."""
    failures = [f for f in (_check_db(), _check_redis()) if f]
    if failures:
        return JsonResponse(
            {"status": "error", "failures": failures},
            status=503,
        )
    return JsonResponse({"status": "ok"})


class UvicornHealthCheckFilter(logging.Filter):
    """Filter out /health/ and /metrics requests from uvicorn access logs."""

    def filter(self, record):
        message = record.getMessage()
        return "/health/" not in message and "/metrics" not in message
