import pytest
from django.contrib.auth import BACKEND_SESSION_KEY
from django.contrib.sessions.backends.db import SessionStore
from django.test import RequestFactory

from django_bpp.middleware import (
    EXTERNAL_AUTH_BACKENDS,
    ConditionalPasswordChangeMiddleware,
)


@pytest.fixture()
def middleware():
    return ConditionalPasswordChangeMiddleware(lambda r: None)


@pytest.fixture()
def authenticated_request(test_user):
    """Request z zalogowanym użytkownikiem i sesją."""
    request = RequestFactory().get("/")
    request.user = test_user
    request.session = SessionStore()
    return request


@pytest.mark.django_db
def test_skips_for_anonymous_user(middleware):
    request = RequestFactory().get("/")
    request.user = type("AnonymousUser", (), {"is_authenticated": False})()
    request.session = SessionStore()
    assert middleware.process_request(request) is None


@pytest.mark.django_db
def test_enforces_for_model_backend(middleware, authenticated_request):
    authenticated_request.session[BACKEND_SESSION_KEY] = (
        "django.contrib.auth.backends.ModelBackend"
    )
    # Middleware próbuje wymusić politykę — nie zwraca None
    # (albo zwraca redirect, albo ustawia klucze sesji).
    # Sprawdzamy, że sesja zawiera klucze password_policies.
    middleware.process_request(authenticated_request)
    assert "_password_policies_last_checked" in authenticated_request.session


@pytest.mark.django_db
def test_skips_for_microsoft_backend(middleware, authenticated_request):
    authenticated_request.session[BACKEND_SESSION_KEY] = (
        "microsoft_auth.backends.MicrosoftAuthenticationBackend"
    )
    result = middleware.process_request(authenticated_request)
    assert result is None
    assert "_password_policies_last_checked" not in authenticated_request.session


@pytest.mark.django_db
def test_skips_for_orcid_backend(middleware, authenticated_request):
    authenticated_request.session[BACKEND_SESSION_KEY] = (
        "orcid_integration.backends.OrcidAuthenticationBackend"
    )
    result = middleware.process_request(authenticated_request)
    assert result is None
    assert "_password_policies_last_checked" not in authenticated_request.session


def test_external_backends_set_is_complete():
    """Upewnia się, że EXTERNAL_AUTH_BACKENDS zawiera oba znane backendy OAuth."""
    assert "microsoft_auth.backends.MicrosoftAuthenticationBackend" in (
        EXTERNAL_AUTH_BACKENDS
    )
    assert "orcid_integration.backends.OrcidAuthenticationBackend" in (
        EXTERNAL_AUTH_BACKENDS
    )
