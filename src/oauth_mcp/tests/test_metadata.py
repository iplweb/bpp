import pytest


@pytest.mark.django_db
def test_metadata_ksztalt(client):
    resp = client.get("/.well-known/oauth-authorization-server")
    assert resp.status_code == 200
    data = resp.json()
    assert data["issuer"].startswith("http")
    assert not data["issuer"].endswith("/o")  # issuer = ROOT
    assert data["authorization_endpoint"].endswith("/o/authorize/")
    assert data["registration_endpoint"].endswith("/o/register/")
    assert data["code_challenge_methods_supported"] == ["S256"]
    assert data["scopes_supported"] == ["read"]


@pytest.mark.django_db
def test_metadata_issuer_z_hosta(client):
    # Host MUSI być w ALLOWED_HOSTS (testy dziedziczą zamkniętą listę) — inaczej
    # DisallowedHost, nie 200 (B3). `test.unexistenttld` jest w ALLOWED_HOSTS.
    resp = client.get(
        "/.well-known/oauth-authorization-server", HTTP_HOST="test.unexistenttld"
    )
    assert "test.unexistenttld" in resp.json()["issuer"]
