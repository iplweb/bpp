"""Minimal URL configuration for auth server.

Only exposes endpoints required for nginx auth_request:
- /__external_auth/is_superuser/ - superuser authentication check
- /health/ - health check for Docker/load balancer
"""

from django.http import HttpResponse
from django.urls import path

from django_bpp.views import is_superuser


def health_check(_request):
    """Simple health check endpoint for Docker healthcheck."""
    return HttpResponse("ok")


urlpatterns = [
    path("__external_auth/is_superuser/", is_superuser, name="is_superuser"),
    path("health/", health_check, name="health"),
]
