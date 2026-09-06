"""BramkaBearera: 401 z WWW-Authenticate, przy zachowaniu dostępu anonimowego.

Bramka MUSI sprawdzać dokładnie to, co StrictOAuth2Authentication: ważność
tokenu, aktywność konta ORAZ scope ``read``. Gdyby sprawdzała mniej, token bez
scope'u przeszedłby tutaj i padł dopiero w DRF — czyli wróciłby jako błąd
w treści JSON-RPC z HTTP 200 i klient nigdy nie ponowiłby autoryzacji
(spec §5.4).
"""

import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker
from oauth2_provider.models import get_access_token_model, get_application_model

from mcp_server.auth import BramkaBearera
from mcp_server.tests.utils import uruchom, wywolaj, zbuduj_scope


async def _ok(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"PRZESZLO"})


def _token(scope="read", aktywny=True, wygasly=False):
    from datetime import timedelta

    from django.utils import timezone

    user = baker.make(get_user_model(), is_active=aktywny)
    app = get_application_model().objects.create(
        name="test",
        client_type="public",
        authorization_grant_type="authorization-code",
    )
    return get_access_token_model().objects.create(
        user=user,
        application=app,
        token="TOKEN123",
        scope=scope,
        expires=timezone.now() + timedelta(seconds=-1 if wygasly else 3600),
    )


@pytest.mark.django_db(transaction=True)
def test_publiczny_bez_naglowka_przepuszcza():
    app = BramkaBearera(_ok, wymagany=False)
    status, _, tresc = uruchom(lambda: wywolaj(app, zbuduj_scope("/mcp")))
    assert status == 200 and tresc == "PRZESZLO"


@pytest.mark.django_db(transaction=True)
def test_wymagany_bez_naglowka_daje_401_z_naglowkiem():
    app = BramkaBearera(_ok, wymagany=True)
    status, naglowki, _ = uruchom(lambda: wywolaj(app, zbuduj_scope("/mcp/auth")))
    assert status == 401
    assert "resource_metadata=" in naglowki["www-authenticate"]


@pytest.mark.django_db(transaction=True)
def test_zly_token_daje_401_takze_na_publicznym():
    app = BramkaBearera(_ok, wymagany=False)
    scope = zbuduj_scope("/mcp", naglowki={"authorization": "Bearer NIEISTNIEJE"})
    status, _, _ = uruchom(lambda: wywolaj(app, scope))
    assert status == 401


@pytest.mark.django_db(transaction=True)
def test_token_bez_scope_read_odrzucony_juz_w_bramce():
    _token(scope="write")
    app = BramkaBearera(_ok, wymagany=False)
    scope = zbuduj_scope("/mcp", naglowki={"authorization": "Bearer TOKEN123"})
    status, _, _ = uruchom(lambda: wywolaj(app, scope))
    assert status == 401


@pytest.mark.django_db(transaction=True)
def test_konto_nieaktywne_odrzucone():
    _token(aktywny=False)
    app = BramkaBearera(_ok, wymagany=False)
    scope = zbuduj_scope("/mcp", naglowki={"authorization": "Bearer TOKEN123"})
    status, _, _ = uruchom(lambda: wywolaj(app, scope))
    assert status == 401


@pytest.mark.django_db(transaction=True)
def test_wazny_token_przechodzi():
    _token()
    app = BramkaBearera(_ok, wymagany=False)
    scope = zbuduj_scope("/mcp", naglowki={"authorization": "Bearer TOKEN123"})
    status, _, tresc = uruchom(lambda: wywolaj(app, scope))
    assert status == 200 and tresc == "PRZESZLO"
