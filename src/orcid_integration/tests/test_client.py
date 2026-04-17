from orcid_integration.client import OrcidClient


def test_get_authorization_url_sandbox():
    client = OrcidClient(
        client_id="APP-TEST",
        client_secret="secret",
        base_url="https://sandbox.orcid.org",
        redirect_uri="https://example.com/orcid/callback/",
    )
    url, state = client.get_authorization_url()

    assert "sandbox.orcid.org/oauth/authorize" in url
    assert "APP-TEST" in url
    assert state


def test_get_authorization_url_production():
    client = OrcidClient(
        client_id="APP-PROD",
        client_secret="secret",
        base_url="https://orcid.org",
        redirect_uri="https://example.com/orcid/callback/",
    )
    url, state = client.get_authorization_url()

    assert "orcid.org/oauth/authorize" in url
    assert "sandbox" not in url


def test_get_authorization_url_contains_scope():
    client = OrcidClient(
        client_id="APP-TEST",
        client_secret="secret",
        base_url="https://sandbox.orcid.org",
        redirect_uri="https://example.com/orcid/callback/",
    )
    url, _state = client.get_authorization_url()

    assert "%2Fauthenticate" in url or "/authenticate" in url
