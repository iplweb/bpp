"""Sekcja ORCID na stronie profilu użytkownika: lista tożsamości + unlink."""

import pytest
from django.test import Client
from django.urls import reverse
from model_bakery import baker

from bpp.models.profile import BppUser
from orcid_integration.models import ORCIDIdentity

PROFILE_URL = reverse("bpp:profil-uzytkownika")


@pytest.fixture
def user_with_password(db):
    user = baker.make(BppUser, username="lukas")
    user.set_password("tajne-haslo-123")
    user.save()
    return user


@pytest.mark.django_db
def test_profile_lists_orcid_identities(uczelnia_with_orcid, user_with_password):
    identity = ORCIDIdentity.objects.create(
        user=user_with_password,
        issuer="https://sandbox.orcid.org",
        sub="0000-0002-1825-0097",
    )
    client = Client()
    client.force_login(user_with_password)

    response = client.get(PROFILE_URL)

    assert identity in list(response.context["orcid_identities"])


@pytest.mark.django_db
def test_unlink_orcid_succeeds_with_usable_password(
    uczelnia_with_orcid, user_with_password
):
    identity = ORCIDIdentity.objects.create(
        user=user_with_password,
        issuer="https://sandbox.orcid.org",
        sub="0000-0002-1825-0097",
    )
    client = Client()
    client.force_login(user_with_password)

    client.post(PROFILE_URL, {"unlink_orcid_identity": identity.pk})

    assert not ORCIDIdentity.objects.filter(pk=identity.pk).exists()


@pytest.mark.django_db
def test_unlink_orcid_blocked_on_self_lockout(uczelnia_with_orcid, db):
    """Konto bez hasła lokalnego nie może odłączyć swojej OSTATNIEJ tożsamości
    ORCID — straciłoby jedyną drogę logowania."""
    user = baker.make(BppUser, username="tylko-orcid")
    user.set_unusable_password()
    user.save()
    identity = ORCIDIdentity.objects.create(
        user=user, issuer="https://sandbox.orcid.org", sub="0000-0002-1825-0097"
    )
    client = Client()
    client.force_login(user)

    client.post(PROFILE_URL, {"unlink_orcid_identity": identity.pk})

    assert ORCIDIdentity.objects.filter(pk=identity.pk).exists()


@pytest.mark.django_db
def test_unlink_orcid_only_own_identity(uczelnia_with_orcid, user_with_password):
    other = baker.make(BppUser, username="obcy")
    foreign = ORCIDIdentity.objects.create(
        user=other, issuer="https://sandbox.orcid.org", sub="0000-0002-1825-0097"
    )
    client = Client()
    client.force_login(user_with_password)

    client.post(PROFILE_URL, {"unlink_orcid_identity": foreign.pk})

    assert ORCIDIdentity.objects.filter(pk=foreign.pk).exists()
