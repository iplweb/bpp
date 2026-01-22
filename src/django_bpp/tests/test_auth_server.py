"""
Integration tests for the lightweight auth server.

Tests the is_superuser endpoint used by nginx auth_request
for protecting services like Grafana and Dozzle.
"""

import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory


def test_auth_server_settings_import():
    """Verify auth_server settings module loads without errors."""
    from django_bpp.settings import auth_server

    assert auth_server.SECRET_KEY is not None
    assert auth_server.DATABASES is not None
    assert auth_server.AUTH_USER_MODEL == "bpp.BppUser"
    assert "bpp" in auth_server.INSTALLED_APPS


def test_is_superuser_unauthenticated_returns_unauthorized():
    """Unauthenticated requests should receive 401 Unauthorized."""
    from django_bpp.views import is_superuser

    rf = RequestFactory()
    request = rf.get("/__external_auth/is_superuser/")
    request.user = AnonymousUser()
    response = is_superuser(request)

    assert response.status_code == 401
    assert response.content == b"unauthorized"


@pytest.mark.django_db
def test_is_superuser_regular_user_gets_forbidden(test_user):
    """Non-superuser should receive 403 Forbidden."""
    from django_bpp.views import is_superuser

    rf = RequestFactory()
    request = rf.get("/__external_auth/is_superuser/")
    request.user = test_user
    response = is_superuser(request)

    assert response.status_code == 403
    assert response.content == b"forbidden"


@pytest.mark.django_db
def test_is_superuser_superuser_gets_ok_with_headers(superuser):
    """Superuser should receive 200 OK with user headers."""
    from django_bpp.views import is_superuser

    rf = RequestFactory()
    request = rf.get("/__external_auth/is_superuser/")
    request.user = superuser
    response = is_superuser(request)

    assert response.status_code == 200
    assert response.content == b"ok"
    assert response["X-WEBAUTH-USER"] == superuser.get_username()
    assert "X-WEBAUTH-EMAIL" in response
    assert "X-WEBAUTH-NAME" in response


def test_auth_server_health_endpoint():
    """Test that health endpoint returns ok."""
    from django_bpp.urls_auth_server import health_check

    rf = RequestFactory()
    request = rf.get("/health/")
    response = health_check(request)

    assert response.status_code == 200
    assert response.content == b"ok"


def test_auth_server_has_rollbar_config():
    """
    Verify auth server settings include ROLLBAR configuration.

    The bpp app's ready() method calls configure_rollbar() which requires
    settings.ROLLBAR to exist. This test ensures the auth server settings
    include ROLLBAR to prevent AttributeError on startup.

    Regression test for: AttributeError: 'Settings' object has no attribute
    'ROLLBAR'
    """
    from django_bpp.settings import auth_server

    assert hasattr(auth_server, "ROLLBAR"), (
        "auth_server settings must include ROLLBAR configuration "
        "because bpp app is in INSTALLED_APPS and calls configure_rollbar()"
    )
    assert isinstance(auth_server.ROLLBAR, dict)
    assert "access_token" in auth_server.ROLLBAR
    assert "environment" in auth_server.ROLLBAR
