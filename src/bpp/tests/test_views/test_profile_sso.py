"""Testy sekcji SSO na stronie profilu — lista tożsamości OIDC oraz
odłączanie z blokadą self-lockout (konto bez hasła nie może usunąć swojej
ostatniej tożsamości SSO — inaczej straciłoby dostęp)."""

import importlib

import pytest
from django.urls import clear_url_caches, reverse
from model_bakery import baker

from oidc_integration.models import OIDCIdentity


@pytest.fixture
def oidc_routing(settings):
    # Trasy OIDC (m.in. ``oidc_integration:polacz``) montują się wg
    # ``OIDC_LOGIN_ENABLED`` przy imporcie ROOT_URLCONF; w testach domyślnie
    # wyłączone. Przeładuj urls z włączoną flagą, by ``{% url %}`` w profilu
    # rozwiązał ``polacz``. Teardown przywraca stan wyłączony.
    import django_bpp.urls

    settings.OIDC_LOGIN_ENABLED = True
    importlib.reload(django_bpp.urls)
    clear_url_caches()
    yield
    settings.OIDC_LOGIN_ENABLED = False
    importlib.reload(django_bpp.urls)
    clear_url_caches()


@pytest.mark.django_db
def test_profile_lists_identities(client, oidc_routing):
    u = baker.make("bpp.BppUser")
    u.set_password("x")
    u.save()
    OIDCIdentity.objects.create(user=u, issuer="https://kc", sub="S")
    client.force_login(u)
    resp = client.get(reverse("bpp:profil-uzytkownika"))
    assert resp.status_code == 200
    assert b"https://kc" in resp.content


@pytest.mark.django_db
def test_profile_shows_link_button_with_existing_identity(client, oidc_routing):
    # Multi-realm UX: „Połącz konto z SSO" widoczny TAKŻE gdy user ma już
    # jakąś tożsamość (można dołożyć powiązanie z kolejnego realmu).
    u = baker.make("bpp.BppUser")
    u.set_password("x")
    u.save()
    OIDCIdentity.objects.create(user=u, issuer="https://kc", sub="S")
    client.force_login(u)
    resp = client.get(reverse("bpp:profil-uzytkownika"))
    assert resp.status_code == 200
    assert reverse("oidc_integration:polacz").encode() in resp.content


@pytest.mark.django_db
def test_unlink_blocked_on_self_lockout(client):
    u = baker.make("bpp.BppUser")
    u.set_unusable_password()
    u.save()
    ident = OIDCIdentity.objects.create(user=u, issuer="kc", sub="S")
    client.force_login(u)
    resp = client.post(
        reverse("bpp:profil-uzytkownika"),
        {"unlink_identity": ident.pk},
    )
    assert OIDCIdentity.objects.filter(pk=ident.pk).exists()
    assert resp.status_code in (200, 302)


@pytest.mark.django_db
def test_unlink_succeeds_with_usable_password(client):
    u = baker.make("bpp.BppUser")
    u.set_password("secret")
    u.save()
    ident = OIDCIdentity.objects.create(user=u, issuer="kc", sub="S")
    client.force_login(u)
    resp = client.post(
        reverse("bpp:profil-uzytkownika"),
        {"unlink_identity": ident.pk},
    )
    assert not OIDCIdentity.objects.filter(pk=ident.pk).exists()
    assert resp.status_code in (200, 302)


@pytest.mark.django_db
def test_unlink_only_own_identity(client):
    u = baker.make("bpp.BppUser")
    u.set_password("secret")
    u.save()
    other = baker.make("bpp.BppUser")
    ident = OIDCIdentity.objects.create(user=other, issuer="kc", sub="S")
    client.force_login(u)
    client.post(
        reverse("bpp:profil-uzytkownika"),
        {"unlink_identity": ident.pk},
    )
    assert OIDCIdentity.objects.filter(pk=ident.pk).exists()
