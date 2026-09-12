"""Audience (RFC 8707) i wyszukiwanie tokenu — znaleziska #4 i #5 z recenzji.

**#4.** Dokument PRM (``oauth_mcp.views_metadata``) deklaruje zasób
``https://<host>/mcp``, a klient MCP zgodny ze specyfikacją autoryzacji
(2025-06-18) MUSI wysłać ``resource=`` z tym adresem — niezależnie od tego, co
w PRM napiszemy (wartość bierze z adresu, pod który się łączy). DOT zapisuje ją
w ``AccessToken.resource``. Bramka ``/mcp`` tego pola nie sprawdzała w ogóle,
a domyślny walidator DOT odrzucał ZA TO żądanie wewnętrzne serwera MCP do
własnego ``/api/v1/`` (prefiks ścieżki ``/mcp`` nie pokrywa ``/api/v1/``).
Skutek zmierzony na pełnym stosie: token zgodnego klienta przechodził bramkę,
po czym KAŻDE wywołanie narzędzia kończyło się ``BppError: Błąd HTTP 401``.

**#5.** Bramka szukała tokenu przez ``.filter(token=raw)``. ``token`` to
niezindeksowany ``TextField``; indeksowaną i unikalną kolumną jest
``token_checksum``, po której szuka sam DOT. Flood błędnymi bearerami skanował
całą tabelę tokenów — na publicznym, nieuwierzytelnionym endpoincie.
"""

import json
from datetime import timedelta

import pytest
from django.contrib.auth import get_user_model
from django.db import connection
from django.test.utils import CaptureQueriesContext
from django.utils import timezone
from model_bakery import baker
from oauth2_provider.models import get_access_token_model, get_application_model

from mcp_server.aplikacja import build_application
from mcp_server.auth import _sprawdz
from mcp_server.routing import RouterHttp
from mcp_server.tests.utils import uruchom, wywolaj, zbuduj_scope

NAGLOWKI_JSONRPC = {
    "content-type": "application/json",
    "accept": "application/json, text/event-stream",
}

INITIALIZE = {
    "jsonrpc": "2.0",
    "id": 1,
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-06-18",
        "capabilities": {},
        "clientInfo": {"name": "test", "version": "0"},
    },
}

WYWOLANIE = {
    "jsonrpc": "2.0",
    "id": 2,
    "method": "tools/call",
    "params": {"name": "szukaj_autora", "arguments": {"nazwisko": "Nazwiskotestowe"}},
}

HOST = "bpp.example.test"
#: ``zbuduj_scope`` daje ``scheme="http"`` i nie ustawia nagłówka proxy, więc
#: kanoniczny adres zasobu dla żądania testowego jest po ``http``.
ZASOB = f"http://{HOST}/mcp"


async def _django(scope, receive, send):
    await send({"type": "http.response.start", "status": 404, "headers": []})
    await send({"type": "http.response.body", "body": b""})


def _router(settings):
    settings.ALLOWED_HOSTS = [HOST]
    mcp_app, start = build_application()
    return RouterHttp(mcp_app, _django, start)


def _token(*, resource, scope="read", surowy="tok-audience"):
    user = baker.make(get_user_model(), is_active=True)
    app = get_application_model().objects.create(
        name="test-mcp",
        client_type="public",
        authorization_grant_type="authorization-code",
    )
    return get_access_token_model().objects.create(
        user=user,
        application=app,
        token=surowy,
        scope=scope,
        expires=timezone.now() + timedelta(hours=1),
        resource=resource,
    )


def _dialog(router, bearer, sciezka="/mcp"):
    naglowki = dict(NAGLOWKI_JSONRPC, authorization=f"Bearer {bearer}")

    async def biegnij():
        wyniki = []
        for cialo in (INITIALIZE, WYWOLANIE):
            scope = zbuduj_scope(sciezka, host=HOST, naglowki=naglowki)
            wyniki.append(await wywolaj(router, scope, cialo))
        return wyniki

    return uruchom(biegnij)


def _dane_narzedzia(tresc):
    odpowiedz = json.loads(tresc)
    assert "error" not in odpowiedz, odpowiedz
    wynik = odpowiedz["result"]
    assert not wynik.get("isError"), wynik
    return json.loads(wynik["content"][0]["text"])


@pytest.mark.django_db(transaction=True)
def test_token_zawezony_do_mcp_dziala_przez_caly_stos(settings, uczelnia, autor):
    """Token zgodnego klienta MCP MUSI dać dane, a nie 401 z ``/api/v1/``.

    Asercja idzie na DANE, nie na status: przed poprawką odpowiedź JSON-RPC też
    miała HTTP 200 — z ``isError`` i komunikatem o błędzie HTTP 401 z żądania
    wewnętrznego. Test na sam status byłby zielony z niewłaściwego powodu.
    """
    autor.nazwisko = "Nazwiskotestowe"
    autor.save()
    _token(resource=[ZASOB])

    router = _router(settings)
    (_, (status, _, tresc)) = _dialog(router, "tok-audience", sciezka="/mcp/auth")

    assert status == 200, tresc
    dane = _dane_narzedzia(tresc)
    assert [a["nazwisko"] for a in dane["autorzy"]] == ["Nazwiskotestowe"]


@pytest.mark.django_db(transaction=True)
def test_token_bez_resource_dalej_dziala(settings, uczelnia, autor):
    """Kompatybilność wstecz: token bez ``resource`` (klient nieimplementujący
    RFC 8707, token założony ręcznie) jest nieograniczony i ma dalej działać —
    ``AccessToken.allows_audience`` zwraca dla pustej listy ``True``."""
    autor.nazwisko = "Nazwiskotestowe"
    autor.save()
    _token(resource=[])

    router = _router(settings)
    (_, (status, _, tresc)) = _dialog(router, "tok-audience", sciezka="/mcp/auth")

    assert status == 200, tresc
    assert _dane_narzedzia(tresc)["laczna_liczba"] == 1


@pytest.mark.django_db(transaction=True)
def test_token_wydany_dla_innego_hosta_odrzucony_w_bramce(settings, uczelnia):
    """Egzekwowanie audience: token zawężony do INNEGO hosta ma dostać 401
    z ``WWW-Authenticate`` (żeby klient poszedł po nowy token), a nie przejść
    bramkę i paść dopiero w środku wywołania narzędzia.

    To jest cały sens sprawdzania audience u nas: w instalacji wielouczelnianej
    tabela tokenów jest wspólna, więc token wydany pod hostem uczelni A bez tej
    kontroli działałby pod hostem uczelni B.
    """
    _token(resource=["https://inna.example.test/mcp"])

    router = _router(settings)
    ((status, naglowki, _), _) = _dialog(router, "tok-audience", sciezka="/mcp/auth")

    assert status == 401
    assert "resource_metadata=" in naglowki["www-authenticate"]


@pytest.mark.django_db(transaction=True)
def test_token_bez_kolumny_token_nadal_znajdowany(uczelnia):
    """Regresja na SPOSÓB wyszukania, nie na jego wynik.

    Odwzorowuje tryb „hashed at rest" DOT (``COMPLIANT_BCP_RFC9700_TOKEN_
    STORAGE``): kolumna ``token`` jest PUSTA, a jedynym śladem tokenu jest
    ``token_checksum``. Wyszukanie przez ``.filter(token=raw)`` nie znajduje tu
    NICZEGO — czyli odmawia dostępu wszystkim. ``queryset.update`` omija
    ``pre_save``, więc checksum zostaje nietknięta, dokładnie jak w DOT.
    """
    token = _token(resource=[])
    get_access_token_model().objects.filter(pk=token.pk).update(token="")

    assert _sprawdz("tok-audience", ZASOB) is True


@pytest.mark.django_db(transaction=True)
def test_wyszukanie_tokenu_uzywa_kolumny_indeksowanej(uczelnia):
    """Bearer z internetu nie może skanować całej tabeli tokenów.

    Asercja na SQL, bo to jedyny sposób odróżnienia „znalazł" od „znalazł
    tanio" — oba warianty dają ten sam wynik logiczny. ``token_checksum`` jest
    ``unique=True, db_index=True``; ``token`` nie ma żadnego indeksu.
    """
    _token(resource=[])

    with CaptureQueriesContext(connection) as zapytania:
        assert _sprawdz("tok-audience", ZASOB) is True

    sql_tokenu = [
        q["sql"]
        for q in zapytania.captured_queries
        if "accesstoken" in q["sql"].lower()
    ]
    assert sql_tokenu, zapytania.captured_queries
    assert all("token_checksum" in sql for sql in sql_tokenu), sql_tokenu
    assert not any('."token" = ' in sql for sql in sql_tokenu), sql_tokenu
