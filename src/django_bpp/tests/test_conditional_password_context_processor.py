import pytest
from django.contrib.auth import BACKEND_SESSION_KEY
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory

from django_bpp.context_processors import conditional_password_status


@pytest.fixture()
def authenticated_request(test_user):
    """Request z zalogowanym użytkownikiem i sesją."""
    request = RequestFactory().get("/")
    request.user = test_user
    request.session = SessionStore()
    return request


@pytest.mark.django_db
def test_returns_empty_for_anonymous_user():
    request = RequestFactory().get("/")
    request.user = type("AnonymousUser", (), {"is_authenticated": False})()
    request.session = SessionStore()
    assert conditional_password_status(request) == {}


@pytest.mark.django_db
def test_skips_for_microsoft_backend(authenticated_request):
    authenticated_request.session[BACKEND_SESSION_KEY] = (
        "microsoft_auth.backends.MicrosoftAuthenticationBackend"
    )
    assert conditional_password_status(authenticated_request) == {
        "password_change_required": False
    }


@pytest.mark.django_db
def test_skips_for_orcid_backend(authenticated_request):
    authenticated_request.session[BACKEND_SESSION_KEY] = (
        "orcid_integration.backends.OrcidAuthenticationBackend"
    )
    assert conditional_password_status(authenticated_request) == {
        "password_change_required": False
    }


@pytest.mark.django_db
def test_delegates_for_model_backend(authenticated_request):
    authenticated_request.session[BACKEND_SESSION_KEY] = (
        "django.contrib.auth.backends.ModelBackend"
    )
    result = conditional_password_status(authenticated_request)
    # Oryginalny password_status zawsze zwraca klucz dla zalogowanego usera.
    assert "password_change_required" in result
