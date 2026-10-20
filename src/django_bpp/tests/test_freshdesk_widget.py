import time

import jwt
import pytest
from django.contrib.auth.models import AnonymousUser
from django.contrib.sessions.backends.cache import SessionStore
from django.template.loader import render_to_string
from django.test import override_settings
from django.urls import reverse
from model_bakery import baker

from bpp.context_processors.freshdesk import freshdesk_widget
from django_bpp.freshdesk import widget_token

WIDGET_ID = "111000000001"
WIDGET_ID_ANON = "222000000002"
SECRET = "sekret-widgetu-freshdesk-do-testow-0123456789"

FRESHDESK = {
    "FRESHDESK_WIDGET_ID": WIDGET_ID,
    "FRESHDESK_WIDGET_ID_ANON": WIDGET_ID_ANON,
    "FRESHDESK_WIDGET_JWT_SECRET": SECRET,
}


@pytest.fixture
def user_z_emailem(django_user_model):
    return baker.make(
        django_user_model,
        username="jkowalski",
        first_name="Jan",
        last_name="Kowalski",
        email="jan.kowalski@example.com",
    )


def _request(rf, user):
    request = rf.get("/")
    request.user = user
    # Część context processorów (np. conditional_password_status) czyta sesję.
    request.session = SessionStore()
    return request


def _render(rf, user):
    return render_to_string("freshdesk_widget.html", request=_request(rf, user))


@override_settings(**FRESHDESK)
def test_context_processor_anonim_dostaje_widget_anon(rf):
    cfg = freshdesk_widget(_request(rf, AnonymousUser()))["FRESHDESK_WIDGET"]
    assert cfg["widget_id"] == WIDGET_ID_ANON
    assert cfg["script_url"].endswith(f"/widgets/{WIDGET_ID_ANON}.js")
    assert cfg["authenticated"] is False
    assert cfg["jwt"] is False


@override_settings(**{**FRESHDESK, "FRESHDESK_WIDGET_ID_ANON": ""})
def test_context_processor_anonim_bez_id_brak_widgetu(rf):
    assert freshdesk_widget(_request(rf, AnonymousUser())) == {"FRESHDESK_WIDGET": None}


@pytest.mark.django_db
@override_settings(**FRESHDESK)
def test_context_processor_zalogowany_dostaje_widget_z_jwt(rf, user_z_emailem):
    cfg = freshdesk_widget(_request(rf, user_z_emailem))["FRESHDESK_WIDGET"]
    assert cfg["widget_id"] == WIDGET_ID
    assert cfg["authenticated"] is True
    assert cfg["jwt"] is True


@pytest.mark.django_db
@override_settings(**{**FRESHDESK, "FRESHDESK_WIDGET_JWT_SECRET": ""})
def test_context_processor_zalogowany_bez_sekretu_bez_jwt(rf, user_z_emailem):
    cfg = freshdesk_widget(_request(rf, user_z_emailem))["FRESHDESK_WIDGET"]
    assert cfg["widget_id"] == WIDGET_ID
    assert cfg["jwt"] is False


@pytest.mark.django_db
@override_settings(TESTING=False, **FRESHDESK)
def test_szablon_anonim(rf):
    html = _render(rf, AnonymousUser())
    assert f'data-widget-id="{WIDGET_ID_ANON}"' in html
    assert "data-token-url" not in html
    assert "data-user-email" not in html
    assert SECRET not in html


@pytest.mark.django_db
@override_settings(TESTING=False, **{**FRESHDESK, "FRESHDESK_WIDGET_ID_ANON": ""})
def test_szablon_anonim_bez_id_nic_nie_renderuje(rf):
    assert "bppSupportButton" not in _render(rf, AnonymousUser())


@pytest.mark.django_db
@override_settings(TESTING=False, **FRESHDESK)
def test_szablon_zalogowany(rf, user_z_emailem):
    html = _render(rf, user_z_emailem)
    assert f'data-widget-id="{WIDGET_ID}"' in html
    assert f'data-token-url="{reverse("freshdesk_widget_token")}"' in html
    assert 'data-user-email="jan.kowalski@example.com"' in html
    assert SECRET not in html


@pytest.mark.django_db
@override_settings(TESTING=True, **FRESHDESK)
def test_szablon_w_testach_nie_renderuje(rf):
    assert "bppSupportButton" not in _render(rf, AnonymousUser())


@pytest.mark.django_db
@override_settings(**FRESHDESK)
def test_widget_token_payload(user_z_emailem):
    now = time.time()
    token = widget_token(user_z_emailem, now=now)
    payload = jwt.decode(token, SECRET, algorithms=["HS256"])
    assert payload["name"] == "Jan Kowalski"
    assert payload["email"] == "jan.kowalski@example.com"
    # Freshdesk: wygaśnięcie maksymalnie 2 godziny w przód.
    assert now < payload["exp"] <= now + 7200


@pytest.mark.django_db
@override_settings(**FRESHDESK)
def test_endpoint_anonim_403(client):
    res = client.get(reverse("freshdesk_widget_token"))
    assert res.status_code == 403
    assert res["Content-Type"] == "application/json"


@pytest.mark.django_db
@override_settings(**FRESHDESK)
def test_endpoint_zalogowany_zwraca_token(client, user_z_emailem):
    client.force_login(user_z_emailem)
    res = client.get(reverse("freshdesk_widget_token"))
    assert res.status_code == 200
    assert "no-cache" in res["Cache-Control"]
    token = res.json()["freshworks_widget_auth_token"]
    payload = jwt.decode(token, SECRET, algorithms=["HS256"])
    assert payload["email"] == "jan.kowalski@example.com"


@pytest.mark.django_db
@override_settings(**{**FRESHDESK, "FRESHDESK_WIDGET_JWT_SECRET": ""})
def test_endpoint_bez_sekretu_404(client, user_z_emailem):
    client.force_login(user_z_emailem)
    assert client.get(reverse("freshdesk_widget_token")).status_code == 404


@pytest.mark.django_db
@override_settings(**FRESHDESK)
def test_endpoint_uzytkownik_bez_emaila_404(client, django_user_model):
    user = baker.make(django_user_model, username="bezmaila", email="")
    client.force_login(user)
    assert client.get(reverse("freshdesk_widget_token")).status_code == 404
