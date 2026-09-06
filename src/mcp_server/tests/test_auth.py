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
    """Asercja na PEŁNY adres, nie na obecność podciągu ``resource_metadata=``.

    Słaba wersja tego testu przepuściła bloker: ``WWW-Authenticate`` wskazywał
    PRM pod ``http://`` na produkcji (schemat brany ze ``scope["scheme"]``,
    któremu uvicorn nie poprawia, bo gunicorn nie ustawia
    ``forwarded_allow_ips``), a asercja na sam podciąg tego nie widziała —
    mimo że zepsute discovery OAuth to jedyny powód, dla którego ten adres
    istnieje.
    """
    app = BramkaBearera(_ok, wymagany=True)
    status, naglowki, _ = uruchom(lambda: wywolaj(app, zbuduj_scope("/mcp/auth")))
    assert status == 401
    assert naglowki["www-authenticate"] == (
        'Bearer resource_metadata="http://bpp.example.test'
        '/.well-known/oauth-protected-resource"'
    )


@pytest.mark.django_db(transaction=True)
def test_prm_ma_https_gdy_proxy_tak_mowi(settings):
    """Produkcja: nginx w osobnym kontenerze, ruch do uvicorna plaintextem.

    Schemat czytamy z nagłówka wskazanego przez ``SECURE_PROXY_SSL_HEADER``,
    a nie z zaszytego ``X-Forwarded-Proto`` — ``settings/base.py`` deklaruje
    ``HTTP_X_FORWARDED_PROTOCOL``, a ``settings/production.py``
    ``HTTP_X_FORWARDED_PROTO``, więc zaszycie jednej nazwy rozjeżdżałoby
    warstwę MCP z Django w jednym z dwóch środowisk.
    """
    settings.SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    app = BramkaBearera(_ok, wymagany=True)
    scope = zbuduj_scope("/mcp/auth", naglowki={"x-forwarded-proto": "https"})
    status, naglowki, _ = uruchom(lambda: wywolaj(app, scope))
    assert status == 401
    assert naglowki["www-authenticate"] == (
        'Bearer resource_metadata="https://bpp.example.test'
        '/.well-known/oauth-protected-resource"'
    )


@pytest.mark.django_db(transaction=True)
def test_prm_ignoruje_naglowek_spoza_ustawienia(settings):
    """Nagłówek INNY niż zadeklarowany w ``SECURE_PROXY_SSL_HEADER`` nie ma
    prawa podnieść schematu — inaczej dowolny klient podnosiłby go sam,
    a Django (które ufa tylko zadeklarowanemu) widziałoby co innego."""
    settings.SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTOCOL", "https")
    app = BramkaBearera(_ok, wymagany=True)
    scope = zbuduj_scope("/mcp/auth", naglowki={"x-forwarded-proto": "https"})
    _, naglowki, _ = uruchom(lambda: wywolaj(app, scope))
    assert 'resource_metadata="http://' in naglowki["www-authenticate"]


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
