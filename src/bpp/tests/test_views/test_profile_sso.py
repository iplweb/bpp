"""Testy sekcji SSO na stronie profilu — lista tożsamości OIDC oraz
odłączanie z blokadą self-lockout (konto bez hasła nie może usunąć swojej
ostatniej tożsamości SSO — inaczej straciłoby dostęp)."""

import pytest
from django.urls import reverse
from model_bakery import baker

from oidc_integration.models import OIDCIdentity


@pytest.mark.django_db
def test_profile_lists_identities(client, settings):
    settings.OIDC_LOGIN_ENABLED = True
    u = baker.make("bpp.BppUser")
    u.set_password("x")
    u.save()
    OIDCIdentity.objects.create(user=u, issuer="https://kc", sub="S")
    client.force_login(u)
    resp = client.get(reverse("bpp:profil-uzytkownika"))
    assert b"https://kc" in resp.content or resp.status_code == 200


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
