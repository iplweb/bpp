"""Testy flow linkowania konta z SSO (``/oidc/polacz/``).

``urlpatterns`` powstają przy imporcie ROOT_URLCONF wg ówczesnego
``OIDC_LOGIN_ENABLED`` — w środowisku testowym OIDC jest domyślnie wyłączone,
więc trasy OIDC (``oidc/polacz/``, ``oidc/authenticate/``) nie są montowane.
Fixture ``oidc_routing`` przeładowuje ROOT_URLCONF z włączoną flagą i czyści
cache resolvera, a w teardownie przywraca stan wyłączony.
"""

import importlib

import pytest
from django.urls import clear_url_caches, reverse
from model_bakery import baker


@pytest.fixture
def oidc_routing(settings):
    import django_bpp.urls

    settings.OIDC_LOGIN_ENABLED = True
    importlib.reload(django_bpp.urls)
    clear_url_caches()
    yield
    settings.OIDC_LOGIN_ENABLED = False
    importlib.reload(django_bpp.urls)
    clear_url_caches()


@pytest.mark.django_db
def test_link_init_requires_password(client, oidc_routing):
    u = baker.make("bpp.BppUser", username="u1")
    u.set_password("secret")
    u.save()
    client.force_login(u)
    resp = client.post(reverse("oidc_integration:polacz"), {"password": "zle"})
    assert resp.status_code == 200
    assert "oidc_link_mode" not in client.session


@pytest.mark.django_db
def test_link_init_sets_session_and_redirects(client, oidc_routing):
    u = baker.make("bpp.BppUser", username="u2")
    u.set_password("secret")
    u.save()
    client.force_login(u)
    resp = client.post(reverse("oidc_integration:polacz"), {"password": "secret"})
    assert resp.status_code == 302
    assert client.session["oidc_link_mode"] is True
    assert client.session["oidc_link_target"] == u.pk


@pytest.mark.django_db
def test_link_init_denies_unusable_password(client, oidc_routing):
    u = baker.make("bpp.BppUser", username="u3")
    u.set_unusable_password()
    u.save()
    client.force_login(u)
    resp = client.post(reverse("oidc_integration:polacz"), {"password": "x"})
    assert resp.status_code == 200
    assert "oidc_link_mode" not in client.session
