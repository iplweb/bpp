import pytest


@pytest.mark.django_db
def test_whoami_wazny_token(access_token, client):
    user, tok = access_token()
    resp = client.get("/api/v1/whoami/", HTTP_AUTHORIZATION=f"Bearer {tok.token}")
    assert resp.status_code == 200
    assert resp.json()["username"] == user.get_username()


@pytest.mark.django_db
def test_whoami_bez_tokenu_401(client):
    resp = client.get("/api/v1/whoami/")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_whoami_niewazny_token_401(client):
    resp = client.get("/api/v1/whoami/", HTTP_AUTHORIZATION="Bearer zly")
    assert resp.status_code == 401


@pytest.mark.django_db
def test_whoami_nieaktywny_user_401(access_token, client):
    user, tok = access_token(is_active=False)
    resp = client.get("/api/v1/whoami/", HTTP_AUTHORIZATION=f"Bearer {tok.token}")
    assert resp.status_code == 401
