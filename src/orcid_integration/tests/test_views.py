from unittest.mock import patch

import pytest
from django.test import Client

from .conftest import ORCID_TEST_ID


@pytest.mark.django_db
def test_orcid_login_redirects_to_orcid(uczelnia_with_orcid):
    client = Client()
    response = client.get("/orcid/login/")

    assert response.status_code == 302
    assert "sandbox.orcid.org/oauth/authorize" in response.url


@pytest.mark.django_db
def test_orcid_login_disabled_returns_404(uczelnia_without_orcid):
    client = Client()
    response = client.get("/orcid/login/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_orcid_login_no_uczelnia(db):
    client = Client()
    response = client.get("/orcid/login/")

    assert response.status_code == 404


@pytest.mark.django_db
def test_orcid_login_stores_next_in_session(uczelnia_with_orcid):
    client = Client()
    client.get("/orcid/login/?next=/some/page/")
    assert client.session.get("orcid_next") == "/some/page/"


@pytest.mark.django_db
def test_orcid_login_rejects_external_next_url(uczelnia_with_orcid):
    client = Client()
    client.get("/orcid/login/?next=https://evil.com/phish")
    assert client.session.get("orcid_next") == "/"


@pytest.mark.django_db
def test_orcid_login_rejects_protocol_relative_next(uczelnia_with_orcid):
    client = Client()
    client.get("/orcid/login/?next=//evil.com/phish")
    assert client.session.get("orcid_next") == "/"


@pytest.mark.django_db
@patch("orcid_integration.views.OrcidClient")
def test_orcid_callback_rejects_external_next_url(
    mock_client_class,
    uczelnia_with_orcid,
    autor_with_orcid,
    bpp_user_matching_autor,
    linked_identity,
):
    mock_instance = mock_client_class.return_value
    mock_instance.fetch_token.return_value = {
        "orcid": ORCID_TEST_ID,
        "name": "Jan Kowalski",
        "access_token": "fake-token",
    }

    client = Client()
    session = client.session
    session["orcid_oauth_state"] = "test-state"
    session["orcid_next"] = "https://evil.com/steal"
    session.save()

    response = client.get("/orcid/callback/?state=test-state&code=auth-code")

    assert response.status_code == 302
    assert response.url == "/"


@pytest.mark.django_db
def test_orcid_callback_invalid_state(uczelnia_with_orcid):
    client = Client()
    # Set a session state
    session = client.session
    session["orcid_oauth_state"] = "correct-state"
    session.save()

    response = client.get("/orcid/callback/?state=wrong-state&code=test-code")

    assert response.status_code == 400


@pytest.mark.django_db
def test_orcid_callback_missing_state(uczelnia_with_orcid):
    client = Client()
    response = client.get("/orcid/callback/?code=test-code")

    assert response.status_code == 400


@pytest.mark.django_db
def test_orcid_callback_orcid_error(uczelnia_with_orcid):
    client = Client()
    session = client.session
    session["orcid_oauth_state"] = "test-state"
    session.save()

    response = client.get("/orcid/callback/?state=test-state&error=access_denied")

    assert response.status_code == 200
    assert "access_denied" in response.content.decode()


@pytest.mark.django_db
@patch("orcid_integration.views.OrcidClient")
def test_orcid_callback_success(
    mock_client_class,
    uczelnia_with_orcid,
    autor_with_orcid,
    bpp_user_matching_autor,
    linked_identity,
):
    mock_instance = mock_client_class.return_value
    mock_instance.fetch_token.return_value = {
        "orcid": ORCID_TEST_ID,
        "name": "Jan Kowalski",
        "access_token": "fake-token",
    }

    client = Client()
    session = client.session
    session["orcid_oauth_state"] = "test-state"
    session["orcid_next"] = "/target/"
    session.save()

    response = client.get("/orcid/callback/?state=test-state&code=auth-code")

    assert response.status_code == 302
    assert response.url == "/target/"


@pytest.mark.django_db
@patch("orcid_integration.views.OrcidClient")
def test_orcid_callback_no_matching_user(
    mock_client_class,
    uczelnia_with_orcid,
):
    mock_instance = mock_client_class.return_value
    mock_instance.fetch_token.return_value = {
        "orcid": "0000-0000-0000-0001",
        "name": "Unknown Person",
        "access_token": "fake-token",
    }

    client = Client()
    session = client.session
    session["orcid_oauth_state"] = "test-state"
    session.save()

    response = client.get("/orcid/callback/?state=test-state&code=auth-code")

    assert response.status_code == 200
    content = response.content.decode()
    assert "Nie znaleziono konta" in content


@pytest.mark.django_db
@patch("orcid_integration.views.OrcidClient")
def test_orcid_callback_token_exchange_failure(
    mock_client_class,
    uczelnia_with_orcid,
):
    mock_instance = mock_client_class.return_value
    mock_instance.fetch_token.side_effect = Exception("Network error")

    client = Client()
    session = client.session
    session["orcid_oauth_state"] = "test-state"
    session.save()

    response = client.get("/orcid/callback/?state=test-state&code=auth-code")

    assert response.status_code == 200
    content = response.content.decode()
    assert "tokenu" in content.lower() or "ORCID" in content
