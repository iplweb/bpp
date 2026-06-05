"""Testy wylogowania OIDC: builder URL-a + backend-aware widok."""

import pytest
from django.contrib.auth import BACKEND_SESSION_KEY, get_user_model
from django.contrib.sessions.backends.db import SessionStore
from django.test import override_settings
from model_bakery import baker

from oidc_integration.logout import build_provider_logout_url
from oidc_integration.views import OIDC_BACKEND_PATH, BppOIDCAwareLogoutView


def _dict_request(rf, **session):
    """Request z sesją-słownikiem (builder nie potrzebuje DB)."""
    req = rf.post("/logout/")
    req.session = dict(session)
    return req


def _db_request(rf, **session):
    """Request z realną sesją DB + pominięciem CSRF (dla widoku LogoutView)."""
    req = rf.post("/logout/")
    req.session = SessionStore()
    for k, v in session.items():
        req.session[k] = v
    req.session.save()
    req._dont_enforce_csrf_checks = True
    return req


@override_settings(OIDC_OP_LOGOUT_ENDPOINT="https://kc/logout", LOGOUT_REDIRECT_URL="/")
def test_build_logout_url_zawiera_id_token_hint_i_redirect(rf):
    req = _dict_request(rf, oidc_id_token="TOK123")
    url = build_provider_logout_url(req)
    assert url.startswith("https://kc/logout?")
    assert "id_token_hint=TOK123" in url
    assert "post_logout_redirect_uri=" in url


@override_settings(OIDC_OP_LOGOUT_ENDPOINT="", LOGOUT_REDIRECT_URL="/start/")
def test_build_logout_url_bez_end_session_to_fallback(rf):
    assert build_provider_logout_url(_dict_request(rf)) == "/start/"


@pytest.mark.django_db
@override_settings(OIDC_OP_LOGOUT_ENDPOINT="https://kc/logout", LOGOUT_REDIRECT_URL="/")
def test_logout_view_sesja_oidc_redirect_do_keycloaka(rf):
    user = baker.make(get_user_model())
    req = _db_request(
        rf, **{BACKEND_SESSION_KEY: OIDC_BACKEND_PATH, "oidc_id_token": "TOK"}
    )
    req.user = user

    resp = BppOIDCAwareLogoutView.as_view()(req)

    assert resp.status_code == 302
    assert resp.url.startswith("https://kc/logout")
    assert "id_token_hint=TOK" in resp.url


@pytest.mark.django_db
@override_settings(OIDC_OP_LOGOUT_ENDPOINT="https://kc/logout", LOGOUT_REDIRECT_URL="/")
def test_logout_view_sesja_haslowa_nie_idzie_do_keycloaka(rf):
    # Inny backend w sesji → standardowe wylogowanie Django (redirect lokalny).
    user = baker.make(get_user_model())
    req = _db_request(
        rf, **{BACKEND_SESSION_KEY: "django.contrib.auth.backends.ModelBackend"}
    )
    req.user = user

    resp = BppOIDCAwareLogoutView.as_view()(req)

    assert resp.status_code == 302
    assert "kc/logout" not in resp.url


# --- Tryb mieszany: MicrosoftLogoutView musi rozpoznać sesję OIDC ---------
# W deploymencie z microsoft_auth + oidc_integration to MicrosoftLogoutView
# obsługuje /logout/ dla WSZYSTKICH backendów (patrz django_bpp/urls.py).
# Sesja OIDC nie może wtedy trafić na logout Microsoftu — inaczej zostaje
# żywa sesja SSO w Keycloaku.


@pytest.mark.django_db
@override_settings(OIDC_OP_LOGOUT_ENDPOINT="https://kc/logout", LOGOUT_REDIRECT_URL="/")
def test_microsoft_logout_view_sesja_oidc_idzie_do_keycloaka(rf):
    from django_bpp.views import MicrosoftLogoutView

    user = baker.make(get_user_model())
    req = _db_request(
        rf, **{BACKEND_SESSION_KEY: OIDC_BACKEND_PATH, "oidc_id_token": "TOK"}
    )
    req.user = user

    resp = MicrosoftLogoutView.as_view()(req)

    assert resp.status_code == 302
    assert resp.url.startswith("https://kc/logout")
    assert "id_token_hint=TOK" in resp.url
    assert "microsoftonline.com" not in resp.url


@pytest.mark.django_db
@override_settings(OIDC_OP_LOGOUT_ENDPOINT="https://kc/logout", LOGOUT_REDIRECT_URL="/")
def test_microsoft_logout_view_sesja_microsoft_idzie_do_microsoftu(rf):
    from django_bpp.views import MicrosoftLogoutView

    user = baker.make(get_user_model())
    req = _db_request(
        rf,
        **{
            BACKEND_SESSION_KEY: (
                "microsoft_auth.backends.MicrosoftAuthenticationBackend"
            )
        },
    )
    req.user = user

    resp = MicrosoftLogoutView.as_view()(req)

    assert resp.status_code == 302
    assert "microsoftonline.com" in resp.url
    assert "kc/logout" not in resp.url
