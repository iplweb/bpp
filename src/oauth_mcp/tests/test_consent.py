import pytest
from model_bakery import baker
from oauth2_provider.models import get_application_model


@pytest.mark.django_db
def test_ekran_zgody_pokazuje_readonly(client, django_user_model):
    # base.html + context-processory BPP wolą mieć Uczelnia (D7).
    baker.make("bpp.Uczelnia")
    Application = get_application_model()
    user = baker.make(django_user_model)
    app = Application.objects.create(
        user=user,
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris="https://claude.ai/cb",
        name="Claude",
    )
    client.force_login(user)
    resp = client.get(
        "/o/authorize/",
        {
            "response_type": "code",
            "client_id": app.client_id,
            "redirect_uri": "https://claude.ai/cb",
            "code_challenge": "x" * 43,
            "code_challenge_method": "S256",
            "scope": "read",
        },
    )
    assert resp.status_code == 200
    assert b"ODCZYT" in resp.content
    assert b"Claude" in resp.content
    # Pola ukryte formularza AllowForm (parametry OAuth) muszą trafić do POST.
    assert b'type="hidden"' in resp.content
    assert b'name="redirect_uri"' in resp.content
    # Checkbox "allow" (BooleanField) nie ma być widoczny — zgodę niosą
    # przyciski submit name="allow", a nieopisany checkbox to osierocone pole.
    assert b'type="checkbox"' not in resp.content


@pytest.mark.django_db
def test_ekran_zgody_bez_widocznego_checkboxa(client, django_user_model):
    # base.html + context-processory BPP wolą mieć Uczelnia (D7).
    baker.make("bpp.Uczelnia")
    Application = get_application_model()
    user = baker.make(django_user_model)
    app = Application.objects.create(
        user=user,
        client_type=Application.CLIENT_PUBLIC,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris="https://claude.ai/cb",
        name="Claude",
    )
    client.force_login(user)
    resp = client.get(
        "/o/authorize/",
        {
            "response_type": "code",
            "client_id": app.client_id,
            "redirect_uri": "https://claude.ai/cb",
            "code_challenge": "x" * 43,
            "code_challenge_method": "S256",
            "scope": "read",
        },
    )
    assert resp.status_code == 200
    # Wszystkie ukryte parametry OAuth muszą przetrwać (potrzebne do POST-a).
    for hidden_name in (
        "redirect_uri",
        "scope",
        "client_id",
        "state",
        "response_type",
        "code_challenge",
        "code_challenge_method",
    ):
        assert f'name="{hidden_name}"'.encode() in resp.content
    # Widoczny, nieopisany checkbox "allow" ma zniknąć — zgodę niosą
    # przyciski submit name="allow".
    assert b'type="checkbox"' not in resp.content
