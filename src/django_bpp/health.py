"""Health check endpoint and log filters for Docker healthcheck probes.

Used by both the main appserver and the lightweight authserver.
Returns a minimal 200 OK response with no database access.
"""

import logging

from django.http import HttpResponse


def health_check(_request):
    """Simple health check endpoint for Docker healthcheck."""
    return HttpResponse("ok")


class UvicornHealthCheckFilter(logging.Filter):
    """Filter out /health/ and /metrics requests from uvicorn access logs."""

    def filter(self, record):
        message = record.getMessage()
        return "/health/" not in message and "/metrics" not in message
