import base64
import json
from importlib import import_module
from unittest.mock import MagicMock, patch
from urllib.parse import urlencode

import pytest
from django.conf import settings
from django.test import RequestFactory, override_settings
from django.urls import reverse
from model_bakery import baker

from bpp.models import Uczelnia
from bpp.models.profile import BppUser
from pbn_api.exceptions import (
    AuthenticationConfigurationError,
    AuthenticationResponseError,
)
from pbn_api.views import (
    PBN_STATE_NONCES_SESSION_KEY,
    TokenLandingPage,
    TokenRedirectPage,
    _issue_state_nonce,
)


class _SessionRequestFactory(RequestFactory):
    """RequestFactory dokładający pustą sesję do każdego żądania."""

    def request(self, **request):
        req = super().request(**request)
        req.session = _new_session()
        return req


def _new_session():
    engine = import_module(settings.SESSION_ENGINE)
    return engine.SessionStore()


@pytest.fixture
def rf():
    return _SessionRequestFactory()


def _state(session, original_page="/admin/publications/", nonce=None):
    """Zwraca ``state`` jak z TokenRedirectPage; nonce zapisany w ``session``
    (chyba że podano ``nonce`` jawnie — wtedy sesja nie jest ruszana)."""
    if nonce is None:
        nonce = _issue_state_nonce(MagicMock(session=session))
    state_data = {
        "originalPage": original_page,
        "timestamp": 1234567890.0,
        "nonce": nonce,
    }
    return base64.b64encode(json.dumps(state_data).encode()).decode()


def _callback_request(rf, user, *, ott="token123", state=None, session=None):
    url = reverse("pbn_api:callback") + f"?ott={ott}"
    if state is not None:
        url += "&" + urlencode({"state": state})
    request = rf.get(url)
    if session is not None:
        request.session = session
    request.user = user
    request._messages = MagicMock()
    return request


def _valid_callback_request(rf, user, original_page="/", **kw):
    session = _new_session()
    state = _state(session, original_page=original_page)
    return _callback_request(rf, user, state=state, session=session, **kw)


@pytest.fixture
def user():
    return baker.make(BppUser, is_active=True)


@pytest.fixture
def uczelnia():
    return baker.make(
        Uczelnia,
        pbn_api_root="https://pbn.example.com",
        pbn_app_name="test_app",
        pbn_app_token="test_token",
    )


@pytest.mark.django_db
def test_token_redirect_page_requires_login(rf):
    """Test TokenRedirectPage redirects unauthenticated users to login"""
    request = rf.get(reverse("pbn_api:authorize"))
    # Add middleware attributes
    request.user = MagicMock()
    request.user.is_authenticated = False

    response = TokenRedirectPage.as_view()(request)

    # Should redirect to login
    assert response.status_code == 302


@pytest.mark.django_db
def test_token_redirect_page_authenticated_user(rf, user, uczelnia):
    """Test TokenRedirectPage returns redirect URL for authenticated user"""
    request = rf.get(reverse("pbn_api:authorize"))
    request.user = user

    view = TokenRedirectPage()
    view.request = request

    with patch("pbn_api.views.OAuthMixin.get_auth_url") as mock_get_auth:
        mock_get_auth.return_value = "https://oauth.example.com/auth"

        url = view.get_redirect_url()

        assert "https://oauth.example.com/auth" in url
        mock_get_auth.assert_called_once()


@pytest.mark.django_db
def test_token_redirect_page_with_next_parameter(rf, user, uczelnia):
    """Test TokenRedirectPage includes 'next' parameter in state"""
    request = rf.get("/pbn_api/authorize/?next=/admin/")
    request.user = user

    view = TokenRedirectPage()
    view.request = request

    with patch("pbn_api.views.OAuthMixin.get_auth_url") as mock_get_auth:
        mock_get_auth.return_value = "https://oauth.example.com/auth"

        view.get_redirect_url()

        # Check that state is included
        mock_get_auth.assert_called_once()
        call_kwargs = mock_get_auth.call_args[1]
        assert "state" in call_kwargs


@pytest.mark.django_db
def test_token_redirect_page_with_referer(rf, user, uczelnia):
    """Test TokenRedirectPage uses HTTP_REFERER when no 'next' parameter"""
    request = rf.get("/pbn_api/authorize/")
    request.META["HTTP_REFERER"] = "https://example.com/previous"
    request.user = user

    view = TokenRedirectPage()
    view.request = request

    with patch("pbn_api.views.OAuthMixin.get_auth_url") as mock_get_auth:
        mock_get_auth.return_value = "https://oauth.example.com/auth"

        view.get_redirect_url()

        mock_get_auth.assert_called_once()


@pytest.mark.django_db
def test_token_redirect_page_state_encoding(rf, user, uczelnia):
    """Test TokenRedirectPage encodes state as base64 JSON"""
    request = rf.get("/pbn_api/authorize/?next=/admin/test")
    request.user = user

    view = TokenRedirectPage()
    view.request = request

    with patch("pbn_api.views.OAuthMixin.get_auth_url") as mock_get_auth:
        mock_get_auth.return_value = "https://oauth.example.com/auth"

        view.get_redirect_url()

        mock_get_auth.assert_called_once()
        call_kwargs = mock_get_auth.call_args[1]
        state = call_kwargs["state"]

        # Decode state and verify it's valid JSON
        decoded = base64.b64decode(state).decode()
        state_data = json.loads(decoded)

        assert "originalPage" in state_data
        assert "timestamp" in state_data


@pytest.mark.django_db
def test_token_landing_page_requires_login(rf):
    """Test TokenLandingPage redirects unauthenticated users to login"""
    request = rf.get(reverse("pbn_api:callback") + "?ott=test123")
    # Add middleware attributes
    request.user = MagicMock()
    request.user.is_authenticated = False

    response = TokenLandingPage.as_view()(request)

    # Should redirect to login
    assert response.status_code == 302


@pytest.mark.django_db
def test_token_landing_page_missing_ott_parameter(rf, user, uczelnia):
    """Test TokenLandingPage handles missing OTT parameter"""
    request = rf.get(reverse("pbn_api:callback"))
    request.user = user

    view = TokenLandingPage()
    view.request = request

    with pytest.raises(TypeError):
        view.get_redirect_url()


_DELAY = "pbn_export_queue.tasks.kolejka_ponow_wysylke_prac_po_zalogowaniu.delay"


def _run_landing(request, token="pbn_user_token_123", side_effect=None):
    view = TokenLandingPage()
    view.request = request
    with (
        patch("pbn_api.views.OAuthMixin.get_user_token") as mock_get_token,
        patch("pbn_api.views.token_set_successfully.send") as mock_signal,
        patch(_DELAY) as mock_delay,
        patch("pbn_api.views.rollbar.report_exc_info"),
    ):
        mock_get_token.return_value = token
        if side_effect is not None:
            mock_get_token.side_effect = side_effect
        url = view.get_redirect_url()
    return url, mock_get_token, mock_signal, mock_delay


@pytest.mark.django_db
@override_settings(PBN_CLIENT_HTTP_TIMEOUT="4,10")
def test_token_landing_page_with_valid_ott(rf, user, uczelnia):
    """Test TokenLandingPage processes valid OTT token"""
    request = _valid_callback_request(rf, user, ott="validtoken123")

    url, mock_get_token, _, _ = _run_landing(request)

    assert url == "/"
    assert mock_get_token.call_args.kwargs["timeout"] == "4,10"


@pytest.mark.django_db
def test_token_landing_page_saves_pbn_token(rf, user, uczelnia):
    """Test TokenLandingPage saves pbn_token to user"""
    request = _valid_callback_request(rf, user, ott="validtoken123")

    _run_landing(request)

    user.refresh_from_db()
    assert user.pbn_token == "pbn_user_token_123"


@pytest.mark.django_db
def test_token_landing_page_with_state_parameter(rf, user, uczelnia):
    """Test TokenLandingPage decodes state parameter"""
    request = _valid_callback_request(rf, user, original_page="/admin/publications/")

    url, _, _, _ = _run_landing(request)

    assert url == "/admin/publications/"


@pytest.mark.django_db
def test_token_landing_page_offhost_original_page_ignored(rf, user, uczelnia):
    """originalPage spoza hosta nie jest używane do przekierowania."""
    request = _valid_callback_request(
        rf, user, original_page="https://example.org/inna-strona/"
    )

    url, _, _, _ = _run_landing(request)

    assert url == "/"
    user.refresh_from_db()
    assert user.pbn_token == "pbn_user_token_123"


@pytest.mark.django_db
def test_token_landing_page_invalid_state_parameter(rf, user, uczelnia):
    """Niedekodowalny state -> brak zapisu tokenu, przekierowanie na /."""
    request = _callback_request(rf, user, state="invalidbase64")

    url, mock_get_token, _, mock_delay = _run_landing(request)

    assert url == "/"
    mock_get_token.assert_not_called()
    mock_delay.assert_not_called()
    user.refresh_from_db()
    assert not user.pbn_token


@pytest.mark.django_db
def test_token_landing_page_without_state_rejected(rf, user, uczelnia):
    """Brak state -> token nie jest pobierany ani zapisywany."""
    request = _callback_request(rf, user)

    url, mock_get_token, mock_signal, mock_delay = _run_landing(request)

    assert url == "/"
    mock_get_token.assert_not_called()
    mock_signal.assert_not_called()
    mock_delay.assert_not_called()
    user.refresh_from_db()
    assert not user.pbn_token
    request._messages.add.assert_called_once()


@pytest.mark.django_db
def test_token_landing_page_state_without_nonce_rejected(rf, user, uczelnia):
    state_data = {"originalPage": "/admin/", "timestamp": 1234567890.0}
    state = base64.b64encode(json.dumps(state_data).encode()).decode()
    request = _callback_request(rf, user, state=state)

    url, mock_get_token, _, _ = _run_landing(request)

    assert url == "/"
    mock_get_token.assert_not_called()
    user.refresh_from_db()
    assert not user.pbn_token


@pytest.mark.django_db
def test_token_landing_page_foreign_nonce_rejected(rf, user, uczelnia):
    """Nonce wydany w innej sesji nie jest akceptowany."""
    other_session = _new_session()
    state = _state(other_session)
    own_session = _new_session()
    _issue_state_nonce(MagicMock(session=own_session))
    request = _callback_request(rf, user, state=state, session=own_session)

    url, mock_get_token, _, _ = _run_landing(request)

    assert url == "/"
    mock_get_token.assert_not_called()
    user.refresh_from_db()
    assert not user.pbn_token
    # nonce tej sesji nie zostaje zużyty przez nieudaną próbę
    assert len(own_session[PBN_STATE_NONCES_SESSION_KEY]) == 1


@pytest.mark.django_db
def test_token_landing_page_nonce_single_use(rf, user, uczelnia):
    """Poprawny nonce działa raz; ponowne użycie tego samego state odpada."""
    session = _new_session()
    state = _state(session)

    first = _callback_request(rf, user, state=state, session=session)
    _, mock_get_token, _, _ = _run_landing(first)
    mock_get_token.assert_called_once()
    assert session[PBN_STATE_NONCES_SESSION_KEY] == []

    user.pbn_token = ""
    user.save()

    second = _callback_request(rf, user, state=state, session=session)
    url, mock_get_token, _, mock_delay = _run_landing(second, token="inny")
    assert url == "/"
    mock_get_token.assert_not_called()
    mock_delay.assert_not_called()
    user.refresh_from_db()
    assert not user.pbn_token


@pytest.mark.django_db
def test_token_redirect_page_stores_nonce_in_session_and_state(rf, user, uczelnia):
    request = rf.get("/pbn_api/authorize/?next=/admin/")
    request.user = user
    view = TokenRedirectPage()
    view.request = request

    with patch("pbn_api.views.OAuthMixin.get_auth_url") as mock_get_auth:
        mock_get_auth.return_value = "https://oauth.example.com/auth"
        view.get_redirect_url()

    state_data = json.loads(
        base64.b64decode(mock_get_auth.call_args.kwargs["state"]).decode()
    )
    assert state_data["nonce"]
    assert request.session[PBN_STATE_NONCES_SESSION_KEY] == [state_data["nonce"]]


@pytest.mark.django_db
def test_token_redirect_then_landing_roundtrip(rf, user, uczelnia):
    """Pełny obieg: authorize -> callback z tym samym state w tej samej sesji."""
    authorize = rf.get("/pbn_api/authorize/?next=/admin/")
    authorize.user = user
    view = TokenRedirectPage()
    view.request = authorize
    with patch("pbn_api.views.OAuthMixin.get_auth_url") as mock_get_auth:
        mock_get_auth.return_value = "https://oauth.example.com/auth"
        view.get_redirect_url()
    state = mock_get_auth.call_args.kwargs["state"]

    request = _callback_request(rf, user, state=state, session=authorize.session)
    url, _, _, _ = _run_landing(request)

    assert url == "/admin/"
    user.refresh_from_db()
    assert user.pbn_token == "pbn_user_token_123"


@pytest.mark.django_db
def test_token_landing_page_authentication_config_error(rf, user, uczelnia):
    """Test TokenLandingPage handles AuthenticationConfigurationError"""
    request = _valid_callback_request(rf, user)

    url, _, _, _ = _run_landing(
        request, side_effect=AuthenticationConfigurationError("Config error")
    )

    assert url == "/"


@pytest.mark.django_db
def test_token_landing_page_authentication_response_error(rf, user, uczelnia):
    """Test TokenLandingPage handles AuthenticationResponseError"""
    request = _valid_callback_request(rf, user)

    url, _, _, _ = _run_landing(request, side_effect=AuthenticationResponseError())

    assert url == "/"
