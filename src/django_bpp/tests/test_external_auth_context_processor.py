import pytest
from django.contrib.auth import BACKEND_SESSION_KEY
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory

from bpp.context_processors.external_auth import external_auth_status


@pytest.fixture()
def authenticated_request(test_user):
    """Request z zalogowanym użytkownikiem i sesją."""
    request = RequestFactory().get("/")
    request.user = test_user
    request.session = SessionStore()
    return request


@pytest.mark.django_db
def test_anonymous_user_is_not_external():
    request = RequestFactory().get("/")
    request.user = type("AnonymousUser", (), {"is_authenticated": False})()
    request.session = SessionStore()
    assert external_auth_status(request) == {"logged_in_via_external_auth": False}


@pytest.mark.django_db
def test_oidc_backend_is_external(authenticated_request):
    authenticated_request.session[BACKEND_SESSION_KEY] = (
        "oidc_integration.backends.BppOIDCBackend"
    )
    assert external_auth_status(authenticated_request) == {
        "logged_in_via_external_auth": True
    }


@pytest.mark.django_db
def test_microsoft_backend_is_external(authenticated_request):
    authenticated_request.session[BACKEND_SESSION_KEY] = (
        "microsoft_auth.backends.MicrosoftAuthenticationBackend"
    )
    assert external_auth_status(authenticated_request) == {
        "logged_in_via_external_auth": True
    }


@pytest.mark.django_db
def test_orcid_backend_is_external(authenticated_request):
    authenticated_request.session[BACKEND_SESSION_KEY] = (
        "orcid_integration.backends.OrcidAuthenticationBackend"
    )
    assert external_auth_status(authenticated_request) == {
        "logged_in_via_external_auth": True
    }


@pytest.mark.django_db
def test_model_backend_is_not_external(authenticated_request):
    authenticated_request.session[BACKEND_SESSION_KEY] = (
        "django.contrib.auth.backends.ModelBackend"
    )
    assert external_auth_status(authenticated_request) == {
        "logged_in_via_external_auth": False
    }


@pytest.mark.django_db
def test_missing_backend_in_session_is_not_external(authenticated_request):
    # Brak klucza backendu w sesji (np. logowanie sprzed wprowadzenia śledzenia)
    # nie może być uznane za logowanie zewnętrzne — bezpieczny default to False.
    assert external_auth_status(authenticated_request) == {
        "logged_in_via_external_auth": False
    }
