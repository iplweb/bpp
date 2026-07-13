"""Flow świadomego wiązania konta z tożsamością ORCID (re-auth hasłem)."""

from unittest.mock import patch

import pytest
from django.test import Client
from model_bakery import baker

from bpp.models.profile import BppUser
from orcid_integration.models import ORCIDIdentity

from .conftest import ORCID_TEST_ID

OTHER_ORCID = "0000-0001-5109-3700"


@pytest.fixture
def user_with_password(db):
    user = baker.make(BppUser, username="lukas")
    user.set_password("tajne-haslo-123")
    user.save()
    return user


# --- ORCIDLinkInitView (re-auth) --------------------------------------------


@pytest.mark.django_db
def test_link_init_requires_login(uczelnia_with_orcid):
    client = Client()
    response = client.get("/orcid/polacz/")
    assert response.status_code == 302
    assert "/login" in response.url or "login" in response.url


@pytest.mark.django_db
def test_link_init_requires_password(uczelnia_with_orcid, user_with_password):
    client = Client()
    client.force_login(user_with_password)
    response = client.post("/orcid/polacz/", {"password": "zle-haslo"})

    assert response.status_code == 200
    assert not client.session.get("orcid_link_mode")


@pytest.mark.django_db
def test_link_init_denies_unusable_password(uczelnia_with_orcid, db):
    user = baker.make(BppUser, username="ldapowiec")
    user.set_unusable_password()
    user.save()

    client = Client()
    client.force_login(user)
    response = client.post("/orcid/polacz/", {"password": ""})

    assert response.status_code == 200
    assert not client.session.get("orcid_link_mode")


@pytest.mark.django_db
def test_link_init_sets_session_and_redirects(uczelnia_with_orcid, user_with_password):
    client = Client()
    client.force_login(user_with_password)
    response = client.post("/orcid/polacz/", {"password": "tajne-haslo-123"})

    assert response.status_code == 302
    assert response.url == "/orcid/login/"
    assert client.session.get("orcid_link_mode") is True
    assert client.session.get("orcid_link_target") == user_with_password.pk


@pytest.mark.django_db
def test_link_init_get_clears_stale_flags(uczelnia_with_orcid, user_with_password):
    client = Client()
    client.force_login(user_with_password)
    session = client.session
    session["orcid_link_mode"] = True
    session["orcid_link_target"] = 999999
    session.save()

    client.get("/orcid/polacz/")

    assert not client.session.get("orcid_link_mode")


# --- callback w trybie link --------------------------------------------------


def _prime_link_session(client, target_pk):
    session = client.session
    session["orcid_oauth_state"] = "state-1"
    session["orcid_link_mode"] = True
    session["orcid_link_target"] = target_pk
    session.save()


@pytest.mark.django_db
@patch("orcid_integration.views.OrcidClient")
def test_callback_link_mode_binds_identity(
    mock_client_class, uczelnia_with_orcid, user_with_password
):
    mock_client_class.return_value.fetch_token.return_value = {"orcid": ORCID_TEST_ID}

    client = Client()
    client.force_login(user_with_password)
    _prime_link_session(client, user_with_password.pk)

    response = client.get("/orcid/callback/?state=state-1&code=c")

    assert response.status_code == 302
    identity = ORCIDIdentity.objects.get(sub=ORCID_TEST_ID)
    assert identity.user_id == user_with_password.pk
    assert identity.issuer == "https://sandbox.orcid.org"
    # flagi trybu link wyczyszczone
    assert not client.session.get("orcid_link_mode")


@pytest.mark.django_db
@patch("orcid_integration.views.OrcidClient")
def test_callback_link_mode_rejects_target_mismatch(
    mock_client_class, uczelnia_with_orcid, user_with_password
):
    mock_client_class.return_value.fetch_token.return_value = {"orcid": ORCID_TEST_ID}

    client = Client()
    client.force_login(user_with_password)
    _prime_link_session(client, 424242)  # cudzy target

    client.get("/orcid/callback/?state=state-1&code=c")

    assert not ORCIDIdentity.objects.filter(sub=ORCID_TEST_ID).exists()


@pytest.mark.django_db
@patch("orcid_integration.views.OrcidClient")
def test_callback_link_mode_rejects_sub_taken_by_other(
    mock_client_class, uczelnia_with_orcid, user_with_password
):
    """Ta (issuer, ORCID iD) należy już do innego konta — nie przejmujemy."""
    other = baker.make(BppUser, username="wlasciciel")
    ORCIDIdentity.objects.create(
        user=other, issuer="https://sandbox.orcid.org", sub=ORCID_TEST_ID
    )
    mock_client_class.return_value.fetch_token.return_value = {"orcid": ORCID_TEST_ID}

    client = Client()
    client.force_login(user_with_password)
    _prime_link_session(client, user_with_password.pk)

    client.get("/orcid/callback/?state=state-1&code=c")

    identity = ORCIDIdentity.objects.get(sub=ORCID_TEST_ID)
    assert identity.user_id == other.pk  # bez zmian


@pytest.mark.django_db
@patch("orcid_integration.views.OrcidClient")
def test_callback_link_mode_idempotent(
    mock_client_class, uczelnia_with_orcid, user_with_password
):
    ORCIDIdentity.objects.create(
        user=user_with_password, issuer="https://sandbox.orcid.org", sub=ORCID_TEST_ID
    )
    mock_client_class.return_value.fetch_token.return_value = {"orcid": ORCID_TEST_ID}

    client = Client()
    client.force_login(user_with_password)
    _prime_link_session(client, user_with_password.pk)

    response = client.get("/orcid/callback/?state=state-1&code=c")

    assert response.status_code == 302
    assert ORCIDIdentity.objects.filter(sub=ORCID_TEST_ID).count() == 1
