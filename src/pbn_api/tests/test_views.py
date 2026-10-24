import base64
import json
import time
from importlib import import_module
from unittest.mock import MagicMock, patch

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
    PBN_PENDING_AUTH_MAX_AGE_SECONDS,
    PBN_PENDING_AUTH_SESSION_KEY,
    TokenLandingPage,
    TokenRedirectPage,
)


class _SessionRequestFactory(RequestFactory):
    """RequestFactory dokładający pustą sesję do każdego żądania."""

    def request(self, **request):
        req = super().request(**request)
        req.session = _new_session()
        req._messages = MagicMock()
        return req


def _new_session():
    engine = import_module(settings.SESSION_ENGINE)
    return engine.SessionStore()


@pytest.fixture
def rf():
    return _SessionRequestFactory()


def _authorize(rf, user, query="", session=None, **meta):
    """GET /pbn_api/authorize (domyślnie jak kliknięcie linku w BPP).

    Zwraca (request, mock_get_auth, response)."""
    meta.setdefault("HTTP_SEC_FETCH_SITE", "same-origin")
    if meta["HTTP_SEC_FETCH_SITE"] is None:
        del meta["HTTP_SEC_FETCH_SITE"]
    request = rf.get("/pbn_api/authorize/" + query, **meta)
    if session is not None:
        request.session = session
    request.user = user
    with patch("pbn_api.views.OAuthMixin.get_auth_url") as mock_get_auth:
        mock_get_auth.return_value = "https://oauth.example.com/auth"
        response = TokenRedirectPage.as_view()(request)
    return request, mock_get_auth, response


def _callback_request(rf, user, *, session, query="?ott=token123"):
    request = rf.get(reverse("pbn_api:callback") + query)
    request.session = session
    request.user = user
    return request


def _authorized_callback_request(rf, user, next_url="/", query="?ott=token123"):
    authorize, _, _ = _authorize(rf, user, query=f"?next={next_url}")
    return _callback_request(rf, user, session=authorize.session, query=query)


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
    _, mock_get_auth, response = _authorize(rf, user)

    assert response.status_code == 302
    assert response["Location"] == "https://oauth.example.com/auth"
    mock_get_auth.assert_called_once()


@pytest.mark.django_db
def test_token_redirect_page_with_next_parameter(rf, user, uczelnia):
    """Test TokenRedirectPage includes 'next' parameter in state"""
    _, mock_get_auth, _ = _authorize(rf, user, query="?next=/admin/")

    mock_get_auth.assert_called_once()
    assert "state" in mock_get_auth.call_args.kwargs


@pytest.mark.django_db
def test_token_redirect_page_with_referer(rf, user, uczelnia):
    """Test TokenRedirectPage uses HTTP_REFERER when no 'next' parameter"""
    request, mock_get_auth, _ = _authorize(
        rf, user, HTTP_REFERER="http://testserver/previous/"
    )

    mock_get_auth.assert_called_once()
    assert (
        request.session[PBN_PENDING_AUTH_SESSION_KEY]["originalPage"]
        == "http://testserver/previous/"
    )


@pytest.mark.django_db
def test_token_redirect_page_state_encoding(rf, user, uczelnia):
    """Test TokenRedirectPage encodes state as base64 JSON"""
    _, mock_get_auth, _ = _authorize(rf, user, query="?next=/admin/test")

    state = mock_get_auth.call_args.kwargs["state"]
    state_data = json.loads(base64.b64decode(state).decode())
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
        patch("pbn_api.autoryzacja.token_set_successfully.send") as mock_signal,
        patch(_DELAY) as mock_delay,
        patch("pbn_api.views.rollbar.report_exc_info"),
    ):
        mock_get_token.return_value = token
        if side_effect is not None:
            mock_get_token.side_effect = side_effect
        url = view.get_redirect_url()
    return url, mock_get_token, mock_signal, mock_delay


def _assert_rejected(request, user, url, mock_get_token, mock_delay):
    assert url == "/"
    mock_get_token.assert_not_called()
    mock_delay.assert_not_called()
    user.refresh_from_db()
    assert not user.pbn_token
    request._messages.add.assert_called_once()


@pytest.mark.django_db
def test_token_redirect_page_stores_pending_auth_in_session(rf, user, uczelnia):
    request, mock_get_auth, _ = _authorize(rf, user, query="?next=/admin/")

    pending = request.session[PBN_PENDING_AUTH_SESSION_KEY]
    assert pending["originalPage"] == "/admin/"
    assert pending["nonce"]
    assert abs(pending["started"] - time.time()) < 60
    state_data = json.loads(
        base64.b64decode(mock_get_auth.call_args.kwargs["state"]).decode()
    )
    assert state_data["nonce"] == pending["nonce"]


@pytest.mark.django_db
def test_token_redirect_page_offhost_next_not_stored(rf, user, uczelnia):
    request, _, _ = _authorize(rf, user, query="?next=https://example.org/x/")

    assert request.session[PBN_PENDING_AUTH_SESSION_KEY]["originalPage"] == "/"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "meta",
    [
        {"HTTP_SEC_FETCH_SITE": "cross-site"},
        {"HTTP_SEC_FETCH_SITE": "same-site"},
        {"HTTP_SEC_FETCH_SITE": "none"},
        {"HTTP_SEC_FETCH_SITE": None},
        {"HTTP_SEC_FETCH_SITE": None, "HTTP_REFERER": "https://example.org/x/"},
        {"HTTP_SEC_FETCH_SITE": None, "HTTP_REFERER": "/wzgledny/"},
    ],
)
def test_token_redirect_page_not_same_origin_shows_interstitial(
    rf, user, uczelnia, meta
):
    request, mock_get_auth, response = _authorize(
        rf, user, query="?next=/admin/", **meta
    )

    assert response.status_code == 200
    mock_get_auth.assert_not_called()
    assert PBN_PENDING_AUTH_SESSION_KEY not in request.session
    content = response.content.decode()
    assert "Za chwilę zalogujesz się w PBN" in content
    assert 'method="post"' in content
    assert "csrfmiddlewaretoken" in content
    assert 'value="/admin/"' in content


@pytest.mark.django_db
def test_token_redirect_page_interstitial_offhost_next_dropped(rf, user, uczelnia):
    _, _, response = _authorize(
        rf, user, query="?next=https://example.org/x/", HTTP_SEC_FETCH_SITE=None
    )

    content = response.content.decode()
    assert '<input type="hidden" name="next" value="/">' in content
    assert 'name="next" value="https://example.org' not in content


@pytest.mark.django_db
def test_token_redirect_page_same_host_referer_without_sec_fetch(rf, user, uczelnia):
    request, mock_get_auth, response = _authorize(
        rf,
        user,
        HTTP_SEC_FETCH_SITE=None,
        HTTP_REFERER="http://testserver/strona/",
    )

    assert response.status_code == 302
    mock_get_auth.assert_called_once()
    assert PBN_PENDING_AUTH_SESSION_KEY in request.session


@pytest.mark.django_db
def test_token_redirect_page_post_without_csrf_forbidden(user, uczelnia):
    from django.test import Client

    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(user)
    with patch("pbn_api.views.OAuthMixin.get_auth_url") as mock_get_auth:
        mock_get_auth.return_value = "https://oauth.example.com/auth"
        response = csrf_client.post(reverse("pbn_api:authorize"), {"next": "/"})

    assert response.status_code == 403
    mock_get_auth.assert_not_called()
    assert PBN_PENDING_AUTH_SESSION_KEY not in csrf_client.session


@pytest.mark.django_db
def test_token_redirect_page_post_with_csrf_starts_auth(user, uczelnia):
    from django.test import Client

    csrf_client = Client(enforce_csrf_checks=True)
    csrf_client.force_login(user)
    with patch("pbn_api.views.OAuthMixin.get_auth_url") as mock_get_auth:
        mock_get_auth.return_value = "https://oauth.example.com/auth"
        page = csrf_client.get(reverse("pbn_api:authorize") + "?next=/admin/")
        assert page.status_code == 200
        token = csrf_client.cookies["csrftoken"].value
        response = csrf_client.post(
            reverse("pbn_api:authorize"),
            {"next": "/admin/", "csrfmiddlewaretoken": token},
        )

    assert response.status_code == 302
    assert response["Location"] == "https://oauth.example.com/auth"
    pending = csrf_client.session[PBN_PENDING_AUTH_SESSION_KEY]
    assert pending["originalPage"] == "/admin/"


@pytest.mark.django_db
def test_token_landing_page_without_state_after_authorize_accepted(rf, user, uczelnia):
    """PBN wraca wyłącznie z ?ott=<uuid> (bez state) — to ma działać."""
    request = _authorized_callback_request(
        rf, user, next_url="/admin/publications/", query="?ott=validtoken123"
    )

    url, mock_get_token, _, _ = _run_landing(request)

    assert url == "/admin/publications/"
    assert mock_get_token.call_args.args[3] == "validtoken123"
    user.refresh_from_db()
    assert user.pbn_token == "pbn_user_token_123"
    assert PBN_PENDING_AUTH_SESSION_KEY not in request.session


@pytest.mark.django_db
@override_settings(PBN_CLIENT_HTTP_TIMEOUT="4,10")
def test_token_landing_page_with_valid_ott(rf, user, uczelnia):
    """Test TokenLandingPage processes valid OTT token"""
    request = _authorized_callback_request(rf, user)

    url, mock_get_token, _, _ = _run_landing(request)

    assert url == "/"
    assert mock_get_token.call_args.kwargs["timeout"] == "4,10"


@pytest.mark.django_db
def test_token_landing_page_ignores_state_parameter(rf, user, uczelnia):
    """originalPage bierzemy z sesji, nie z parametru state."""
    state = base64.b64encode(
        json.dumps({"originalPage": "/inna-strona/"}).encode()
    ).decode()
    request = _authorized_callback_request(
        rf, user, next_url="/admin/", query=f"?ott=token123&state={state}"
    )

    url, _, _, _ = _run_landing(request)

    assert url == "/admin/"


@pytest.mark.django_db
def test_token_landing_page_offhost_original_page_ignored(rf, user, uczelnia):
    session = _new_session()
    session[PBN_PENDING_AUTH_SESSION_KEY] = {
        "nonce": "x",
        "started": time.time(),
        "originalPage": "https://example.org/inna-strona/",
    }
    request = _callback_request(rf, user, session=session)

    url, _, _, _ = _run_landing(request)

    assert url == "/"
    user.refresh_from_db()
    assert user.pbn_token == "pbn_user_token_123"


@pytest.mark.django_db
def test_token_landing_page_without_pending_auth_rejected(rf, user, uczelnia):
    request = _callback_request(rf, user, session=_new_session())

    url, mock_get_token, mock_signal, mock_delay = _run_landing(request)

    _assert_rejected(request, user, url, mock_get_token, mock_delay)
    mock_signal.assert_not_called()


@pytest.mark.django_db
def test_token_landing_page_rejected_does_not_call_pbn(rf, user, uczelnia):
    """Odrzucony callback nie wymienia ott w PBN i nie rusza innych sesji."""
    other, _, _ = _authorize(rf, user)
    other_pending = dict(other.session[PBN_PENDING_AUTH_SESSION_KEY])

    request = _callback_request(rf, user, session=_new_session())
    view = TokenLandingPage()
    view.request = request
    with (
        patch("pbn_api.autoryzacja.OAuthMixin") as mock_oauth,
        patch(_DELAY) as mock_delay,
    ):
        url = view.get_redirect_url()

    assert url == "/"
    assert mock_oauth.mock_calls == []
    mock_delay.assert_not_called()
    assert other.session[PBN_PENDING_AUTH_SESSION_KEY] == other_pending


@pytest.mark.django_db
def test_token_landing_page_pending_auth_single_use(rf, user, uczelnia):
    first = _authorized_callback_request(rf, user)
    _, mock_get_token, _, _ = _run_landing(first)
    mock_get_token.assert_called_once()

    user.pbn_token = ""
    user.save()

    second = _callback_request(rf, user, session=first.session)
    url, mock_get_token, _, mock_delay = _run_landing(second, token="inny")

    _assert_rejected(second, user, url, mock_get_token, mock_delay)


@pytest.mark.django_db
def test_token_landing_page_pending_auth_consumed_on_failure(rf, user, uczelnia):
    """Wpis jest zużywany także przy nieudanym pobraniu tokenu."""
    first = _authorized_callback_request(rf, user)
    _run_landing(first, side_effect=AuthenticationResponseError())
    assert PBN_PENDING_AUTH_SESSION_KEY not in first.session

    second = _callback_request(rf, user, session=first.session)
    url, mock_get_token, _, mock_delay = _run_landing(second)

    _assert_rejected(second, user, url, mock_get_token, mock_delay)


@pytest.mark.django_db
def test_token_landing_page_expired_pending_auth_rejected(rf, user, uczelnia):
    authorize, _, _ = _authorize(rf, user)
    request = _callback_request(rf, user, session=authorize.session)

    later = time.time() + PBN_PENDING_AUTH_MAX_AGE_SECONDS + 5
    with patch("pbn_api.views.timezone.now") as mock_now:
        mock_now.return_value.timestamp.return_value = later
        url, mock_get_token, _, mock_delay = _run_landing(request)

    _assert_rejected(request, user, url, mock_get_token, mock_delay)
    assert PBN_PENDING_AUTH_SESSION_KEY not in request.session


@pytest.mark.django_db
def test_token_landing_page_malformed_pending_auth_rejected(rf, user, uczelnia):
    session = _new_session()
    session[PBN_PENDING_AUTH_SESSION_KEY] = "cokolwiek"
    request = _callback_request(rf, user, session=session)

    url, mock_get_token, _, mock_delay = _run_landing(request)

    _assert_rejected(request, user, url, mock_get_token, mock_delay)


@pytest.mark.django_db
def test_token_landing_page_authentication_config_error(rf, user, uczelnia):
    """Test TokenLandingPage handles AuthenticationConfigurationError"""
    request = _authorized_callback_request(rf, user)

    url, _, _, _ = _run_landing(
        request, side_effect=AuthenticationConfigurationError("Config error")
    )

    assert url == "/"


@pytest.mark.django_db
def test_token_landing_page_authentication_response_error(rf, user, uczelnia):
    """Test TokenLandingPage handles AuthenticationResponseError"""
    request = _authorized_callback_request(rf, user)

    url, _, _, _ = _run_landing(request, side_effect=AuthenticationResponseError())

    assert url == "/"
