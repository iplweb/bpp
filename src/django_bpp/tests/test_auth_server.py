"""
Integration tests for the lightweight auth server.

Tests the is_superuser endpoint used by nginx auth_request
for protecting services like Grafana and Dozzle.
"""

import pytest
from django.test import RequestFactory
from django.urls import reverse


def test_auth_server_settings_import():
    """Verify auth_server settings module loads without errors."""
    from django_bpp.settings import auth_server

    assert auth_server.SECRET_KEY is not None
    assert auth_server.DATABASES is not None
    assert auth_server.AUTH_USER_MODEL == "bpp.BppUser"
    assert "bpp" in auth_server.INSTALLED_APPS


@pytest.mark.django_db
def test_is_superuser_unauthenticated_redirects_to_login(client):
    """Unauthenticated requests should redirect to login."""
    url = reverse("is_superuser")
    response = client.get(url)

    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_is_superuser_regular_user_gets_forbidden(logged_in_client):
    """Non-superuser should receive 403 Forbidden."""
    url = reverse("is_superuser")
    response = logged_in_client.get(url)

    assert response.status_code == 403
    assert response.content == b"forbidden"


@pytest.mark.django_db
def test_is_superuser_superuser_gets_ok_with_headers(superuser_client, superuser):
    """Superuser should receive 200 OK with user headers."""
    url = reverse("is_superuser")
    response = superuser_client.get(url)

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
