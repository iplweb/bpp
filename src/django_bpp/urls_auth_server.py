"""Minimal URL configuration for auth server.

Exposes endpoints for nginx auth_request and emergency login:
- /__external_auth/is_superuser/ - superuser authentication check
- /__auth/login/ - emergency login form
- /health/ - health check for Docker/load balancer
"""

from django.contrib.auth.views import LoginView
from django.http import HttpResponse
from django.urls import path

from django_bpp.views import is_superuser


def health_check(_request):
    """Simple health check endpoint for Docker healthcheck."""
    return HttpResponse("ok")


urlpatterns = [
    path("__external_auth/is_superuser/", is_superuser, name="is_superuser"),
    path(
        "__external_auth/login/",
        LoginView.as_view(template_name="auth_server/login.html"),
        name="login",
    ),
    path("health/", health_check, name="health"),
]
