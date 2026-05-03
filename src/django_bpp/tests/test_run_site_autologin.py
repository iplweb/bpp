"""Testy widoku auto-login dla `manage.py run_site`."""

from __future__ import annotations

import pytest
from django.test import RequestFactory
from model_bakery import baker

from django_bpp.views_run_site_autologin import (
    AUTOLOGIN_ENV_VAR,
    run_site_autologin,
)


@pytest.fixture
def admin_user(db):
    User = _user_model()
    return baker.make(User, username="admin", is_active=True, is_staff=True)


def _user_model():
    from django.contrib.auth import get_user_model

    return get_user_model()


@pytest.mark.django_db
def test_autologin_returns_404_without_env(monkeypatch):
    monkeypatch.delenv(AUTOLOGIN_ENV_VAR, raising=False)
    rf = RequestFactory()
    req = _attach_session(rf.get("/x/?token=abc"))
    from django.http import Http404

    with pytest.raises(Http404):
        run_site_autologin(req)


@pytest.mark.django_db
def test_autologin_returns_404_on_wrong_token(monkeypatch, admin_user):
    monkeypatch.setenv(AUTOLOGIN_ENV_VAR, "secret-token")
    rf = RequestFactory()
    req = _attach_session(rf.get("/x/?token=wrong"))
    from django.http import Http404

    with pytest.raises(Http404):
        run_site_autologin(req)


@pytest.mark.django_db
def test_autologin_sets_cookielaw_accepted_cookie(monkeypatch, admin_user):
    """Po udanym auto-loginie response ma cookie cookielaw_accepted=1, żeby
    cookie banner się nie pokazywał (run_site to lokalny dev — banner irytuje)."""
    monkeypatch.setenv(AUTOLOGIN_ENV_VAR, "secret-token")
    rf = RequestFactory()
    req = _attach_session(rf.get("/x/?token=secret-token"))

    response = run_site_autologin(req)

    assert response.status_code == 302
    assert response.url == "/"
    assert "cookielaw_accepted" in response.cookies
    cookie = response.cookies["cookielaw_accepted"]
    assert cookie.value == "1"
    assert cookie["max-age"] > 0
    assert cookie["samesite"].lower() == "lax"
    assert cookie["path"] == "/"


def _attach_session(request):
    """Dodaj session + messages middleware do request (login() ich potrzebuje)."""
    from django.contrib.messages.storage.fallback import FallbackStorage
    from django.contrib.sessions.backends.db import SessionStore

    request.session = SessionStore()
    request._messages = FallbackStorage(request)
    return request
