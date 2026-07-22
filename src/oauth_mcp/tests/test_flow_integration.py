import base64
import hashlib

import pytest
from model_bakery import baker
from oauth2_provider.models import get_application_model


def _pkce():
    verifier = "a" * 64
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest())
        .decode()
        .rstrip("=")
    )
    return verifier, challenge


@pytest.mark.django_db
def test_pelny_taniec_pkce_i_token(client, django_user_model):
    Application = get_application_model()
    user = baker.make(django_user_model, is_active=True)
    app = Application.objects.create(
        user=user,
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris="https://claude.ai/cb",
        name="Claude",
    )
    client.force_login(user)
    verifier, challenge = _pkce()
    resp = client.post(
        "/o/authorize/",
        {
            "response_type": "code",
            "client_id": app.client_id,
            "redirect_uri": "https://claude.ai/cb",
            "scope": "read",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "allow": "Authorize",
        },
    )
    assert resp.status_code == 302
    code = resp["Location"].split("code=")[1].split("&")[0]

    token_resp = client.post(
        "/o/token/",
        {
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": "https://claude.ai/cb",
            "client_id": app.client_id,
            "code_verifier": verifier,
        },
    )
    assert token_resp.status_code == 200
    body = token_resp.json()
    assert body["token_type"].lower() == "bearer"
    assert body["scope"] == "read"

    # token działa na whoami
    who = client.get(
        "/api/v1/whoami/", HTTP_AUTHORIZATION=f"Bearer {body['access_token']}"
    )
    assert who.status_code == 200
    assert who.json()["id"] == user.pk

    # rotacja refresh (spec §10/§13/W2)
    refresh = body["refresh_token"]
    r1 = client.post(
        "/o/token/",
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": app.client_id,
        },
    )
    assert r1.status_code == 200
    assert r1.json()["refresh_token"] != refresh  # ROTATE_REFRESH_TOKEN
    # stary refresh już nieważny
    r2 = client.post(
        "/o/token/",
        {
            "grant_type": "refresh_token",
            "refresh_token": refresh,
            "client_id": app.client_id,
        },
    )
    assert r2.status_code == 400


@pytest.mark.django_db
def test_revoke_uniewaznia_token(access_token, client):
    """Revoke → kolejny request/whoami → 401 (spec §10/§13/W2)."""
    user, tok = access_token()
    resp = client.post(
        "/o/revoke_token/",
        {"token": tok.token, "client_id": tok.application.client_id},
    )
    assert resp.status_code == 200
    who = client.get("/api/v1/whoami/", HTTP_AUTHORIZATION=f"Bearer {tok.token}")
    assert who.status_code == 401
