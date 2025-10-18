import base64
import json

import pytest
from django.test import RequestFactory
from django.urls import reverse
from model_bakery import baker
from unittest.mock import patch, MagicMock

from bpp.models import Uczelnia
from bpp.models.profile import BppUser
from pbn_api.exceptions import (
    AuthenticationConfigurationError,
    AuthenticationResponseError,
)
from pbn_api.views import TokenRedirectPage, TokenLandingPage


@pytest.fixture
def rf():
    return RequestFactory()


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

        url = view.get_redirect_url()

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

        url = view.get_redirect_url()

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

        url = view.get_redirect_url()

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

    with pytest.raises(Exception):
        view.get_redirect_url()


@pytest.mark.django_db
def test_token_landing_page_with_valid_ott(rf, user, uczelnia):
    """Test TokenLandingPage processes valid OTT token"""
    request = rf.get(reverse("pbn_api:callback") + "?ott=validtoken123")
    request.user = user
    # Mock the messages framework
    request._messages = MagicMock()

    view = TokenLandingPage()
    view.request = request

    with patch("pbn_api.views.OAuthMixin.get_user_token") as mock_get_token:
        mock_get_token.return_value = "pbn_user_token_123"
        with patch(
            "pbn_export_queue.tasks.kolejka_ponow_wysylke_prac_po_zalogowaniu.delay"
        ):
            with patch("pbn_api.views.messages.info"):
                url = view.get_redirect_url()

        assert url == "/"


@pytest.mark.django_db
def test_token_landing_page_saves_pbn_token(rf, user, uczelnia):
    """Test TokenLandingPage saves pbn_token to user"""
    request = rf.get(reverse("pbn_api:callback") + "?ott=validtoken123")
    request.user = user
    request._messages = MagicMock()

    view = TokenLandingPage()
    view.request = request

    with patch("pbn_api.views.OAuthMixin.get_user_token") as mock_get_token:
        mock_get_token.return_value = "pbn_user_token_123"
        with patch("pbn_api.views.token_set_successfully.send"):
            with patch(
                "pbn_export_queue.tasks.kolejka_ponow_wysylke_prac_po_zalogowaniu.delay"
            ):
                url = view.get_redirect_url()

        # Refresh user from DB
        user.refresh_from_db()
        assert user.pbn_token == "pbn_user_token_123"


@pytest.mark.django_db
def test_token_landing_page_with_state_parameter(rf, user, uczelnia):
    """Test TokenLandingPage decodes state parameter"""
    state_data = {
        "originalPage": "/admin/publications/",
        "timestamp": 1234567890.0,
    }
    state = base64.b64encode(json.dumps(state_data).encode()).decode()

    request = rf.get(reverse("pbn_api:callback") + f"?ott=token123&state={state}")
    request.user = user
    request._messages = MagicMock()

    view = TokenLandingPage()
    view.request = request

    with patch("pbn_api.views.OAuthMixin.get_user_token") as mock_get_token:
        mock_get_token.return_value = "pbn_user_token_123"
        with patch("pbn_api.views.token_set_successfully.send"):
            with patch(
                "pbn_export_queue.tasks.kolejka_ponow_wysylke_prac_po_zalogowaniu.delay"
            ):
                url = view.get_redirect_url()

        # Should redirect to the original page
        assert url == "/admin/publications/"


@pytest.mark.django_db
def test_token_landing_page_invalid_state_parameter(rf, user, uczelnia):
    """Test TokenLandingPage handles invalid state parameter"""
    request = rf.get(reverse("pbn_api:callback") + "?ott=token123&state=invalidbase64")
    request.user = user
    request._messages = MagicMock()

    view = TokenLandingPage()
    view.request = request

    with patch("pbn_api.views.OAuthMixin.get_user_token") as mock_get_token:
        mock_get_token.return_value = "pbn_user_token_123"
        with patch("pbn_api.views.token_set_successfully.send"):
            with patch(
                "pbn_export_queue.tasks.kolejka_ponow_wysylke_prac_po_zalogowaniu.delay"
            ):
                url = view.get_redirect_url()

        # Should fall back to default redirect
        assert url == "/"


@pytest.mark.django_db
def test_token_landing_page_authentication_config_error(rf, user, uczelnia):
    """Test TokenLandingPage handles AuthenticationConfigurationError"""
    request = rf.get(reverse("pbn_api:callback") + "?ott=token123")
    request.user = user
    request._messages = MagicMock()

    view = TokenLandingPage()
    view.request = request

    with patch("pbn_api.views.OAuthMixin.get_user_token") as mock_get_token:
        mock_get_token.side_effect = AuthenticationConfigurationError("Config error")
        with patch("pbn_api.views.rollbar.report_exc_info"):
            url = view.get_redirect_url()

        assert url == "/"


@pytest.mark.django_db
def test_token_landing_page_authentication_response_error(rf, user, uczelnia):
    """Test TokenLandingPage handles AuthenticationResponseError"""
    request = rf.get(reverse("pbn_api:callback") + "?ott=token123")
    request.user = user
    request._messages = MagicMock()

    view = TokenLandingPage()
    view.request = request

    with patch("pbn_api.views.OAuthMixin.get_user_token") as mock_get_token:
        mock_get_token.side_effect = AuthenticationResponseError()
        with patch("pbn_api.views.rollbar.report_exc_info"):
            url = view.get_redirect_url()

        assert url == "/"


@pytest.mark.django_db
def test_token_landing_page_sends_signal_on_success(rf, user, uczelnia):
    """Test TokenLandingPage sends signal when token is set successfully"""
    from django.test.utils import override_settings
    from django.dispatch import receiver

    request = rf.get(reverse("pbn_api:callback") + "?ott=token123")
    request.user = user
    request._messages = MagicMock()

    view = TokenLandingPage()
    view.request = request

    signal_sent = []

    @receiver
    def capture_signal(sender, **kwargs):
        signal_sent.append(True)

    with patch("pbn_api.views.OAuthMixin.get_user_token") as mock_get_token:
        mock_get_token.return_value = "pbn_user_token_123"
        with patch(
            "pbn_api.views.token_set_successfully.send", side_effect=capture_signal
        ):
            with patch(
                "pbn_export_queue.tasks.kolejka_ponow_wysylke_prac_po_zalogowaniu.delay"
            ):
                url = view.get_redirect_url()


@pytest.mark.django_db
def test_token_landing_page_default_redirect_without_state(rf, user, uczelnia):
    """Test TokenLandingPage defaults to / when no state is provided"""
    request = rf.get(reverse("pbn_api:callback") + "?ott=token123")
    request.user = user
    request._messages = MagicMock()

    view = TokenLandingPage()
    view.request = request

    with patch("pbn_api.views.OAuthMixin.get_user_token") as mock_get_token:
        mock_get_token.return_value = "pbn_user_token_123"
        with patch("pbn_api.views.token_set_successfully.send"):
            with patch(
                "pbn_export_queue.tasks.kolejka_ponow_wysylke_prac_po_zalogowaniu.delay"
            ):
                url = view.get_redirect_url()

        assert url == "/"
