import pytest
from model_bakery import baker
from oauth2_provider.models import get_application_model


@pytest.mark.django_db
def test_authorize_niezalogowany_redirect_na_login(client):
    resp = client.get("/o/authorize/", {"response_type": "code"})
    assert resp.status_code == 302
    assert "/accounts/login/" in resp["Location"]


@pytest.mark.django_db
def test_pkce_wymagane(client, django_user_model):
    Application = get_application_model()
    user = baker.make(django_user_model)
    app = Application.objects.create(
        user=user,
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris="https://claude.ai/callback",
        name="test",
    )
    client.force_login(user)
    # authorize BEZ code_challenge → odrzucone (PKCE_REQUIRED)
    resp = client.get(
        "/o/authorize/",
        {
            "response_type": "code",
            "client_id": app.client_id,
            "redirect_uri": "https://claude.ai/callback",
        },
    )
    # DOT przy PKCE_REQUIRED i braku code_challenge zwraca redirectowalny błąd:
    # 302 z ?error=... na redirect_uri (nie 400).
    assert resp.status_code == 302
    assert "error=" in resp["Location"]


@pytest.mark.django_db
def test_device_flow_niedostepny(client):
    # RFC 8628 Device Authorization Grant świadomie NIE jest zamontowany —
    # niechciany w MVP (nieuwierzytelniony, csrf-exempt, nielimitowany zapis
    # DeviceGrant). Montujemy tylko authorize/token/revoke, patrz urls.py.
    resp = client.post("/o/device-authorization/")
    assert resp.status_code == 404
