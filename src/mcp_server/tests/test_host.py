"""Nagłówek ``Host`` na ścieżce ``/mcp``: walidacja jak w Django, port dozwolony.

Dwie usterki z recenzji PR #804, obie o ten sam nagłówek i obie niewidoczne dla
wcześniejszych testów, bo te używały wyłącznie hostów BEZ portu:

1. Host z NIEPOPRAWNYM portem (``<uczelnia>:abc``) przechodził wszystkie cztery
   warstwy — allowlistę SDK (dopasowuje ``host:*`` przez ``startswith``, portu
   nie waliduje), bramkę uczelni (obcinała port ``split(":")[0]``) — i wysypywał
   się dopiero w ``httpx.URL`` przy budowie ``base_url``. Ten wyjątek nie jest
   ani ``httpx.HTTPError``, ani ``BppError``, więc wrapper narzędzi zgłaszał go
   do Rollbara: jedno anonimowe żądanie = jedno zgłoszenie, bez rate-limitu.
2. Host z PRAWIDŁOWYM portem (``localhost:54321``, czyli dokładnie to, co daje
   ``run-site run`` pod Daphne) psuł KAŻDE wywołanie narzędzia, bo
   ``mcp_server.klient`` porównywał ``httpx.URL.host`` (nigdy nie zawiera portu)
   z surowym nagłówkiem ``Host`` (zawiera).
"""

import json
from unittest.mock import Mock

import httpx
import pytest
from bpp_mcp.client import BppError

from mcp_server import aplikacja as modul_aplikacji
from mcp_server import routing as modul_routingu
from mcp_server.aplikacja import build_application
from mcp_server.klient import BppClientInProcess
from mcp_server.kontekst import DaneZadania, dane_zadania, domena_hosta
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
    "params": {
        "name": "szukaj_autora",
        "arguments": {"nazwisko": "Nazwiskotestowe"},
    },
}


async def _django(scope, receive, send):
    await send({"type": "http.response.start", "status": 404, "headers": []})
    await send({"type": "http.response.body", "body": b""})


def _router(settings):
    settings.ALLOWED_HOSTS = ["bpp.example.test"]
    mcp_app, start = build_application()
    return RouterHttp(mcp_app, _django, start)


def _dialog(router, host):
    """``initialize`` + ``tools/call`` w JEDNEJ pętli zdarzeń (patrz test_e2e)."""

    async def biegnij():
        wyniki = []
        for cialo in (INITIALIZE, WYWOLANIE):
            scope = zbuduj_scope("/mcp", host=host, naglowki=NAGLOWKI_JSONRPC)
            wyniki.append(await wywolaj(router, scope, cialo))
        return wyniki

    return uruchom(biegnij)


def test_domena_hosta_odrzuca_to_samo_co_django():
    """Jednostkowo: ``domena_hosta`` musi być zgodne z ``get_host()`` Django.

    Przypadki niepoprawne to dokładnie te, które przechodziły przez allowlistę
    SDK (``host.startswith(base + ":")``) — port nieliczbowy, podwójny port,
    port szesnastkowy, port pusty.
    """
    assert domena_hosta("bpp.example.test") == "bpp.example.test"
    assert domena_hosta("BPP.Example.Test:8000") == "bpp.example.test"
    assert domena_hosta("bpp.example.test.:8000") == "bpp.example.test"
    assert domena_hosta("[::1]:8000") == "[::1]"
    for zly in (
        "bpp.example.test:abc",
        "bpp.example.test:1:2",
        "bpp.example.test:0x1F",
    ):
        assert domena_hosta(zly) == "", zly


@pytest.mark.django_db(transaction=True)
def test_host_z_niepoprawnym_portem_daje_421_i_nie_woła_rollbara(
    settings, uczelnia, autor, monkeypatch
):
    """Regresja na anonimowy, nielimitowany kanał do Rollbara.

    Asercja jest DWUCZĘŚCIOWA i obie części są potrzebne:

    * ``status == 421`` — samo to nie wystarcza, bo przed poprawką odpowiedź
      miała status 200 (błąd narzędzia jedzie w ``isError``), więc test
      sprawdzający tylko „nie 500" byłby zielony z niewłaściwego powodu;
    * ``report_exc_info`` NIE wywołane — to jest właściwa szkoda. Zmierzone na
      kodzie sprzed poprawki: 200 + DOKŁADNIE JEDNO zgłoszenie na żądanie,
      czyli ``curl`` w pętli wyczerpuje kwotę Rollbara.

    Mockujemy Rollbara w OBU modułach, które go wołają (``aplikacja``
    — wrapper narzędzi, ``routing`` — siatka bezpieczeństwa), żeby test nie
    przeszedł przypadkiem dlatego, że wyjątek przewędrował do innej warstwy.
    """
    autor.nazwisko = "Nazwiskotestowe"
    autor.save()
    rollbar_narzedzi = Mock()
    rollbar_routingu = Mock()
    monkeypatch.setattr(modul_aplikacji, "rollbar", rollbar_narzedzi)
    monkeypatch.setattr(modul_routingu, "rollbar", rollbar_routingu)

    router = _router(settings)
    (_, (status, _, tresc)) = _dialog(router, "bpp.example.test:abc")

    assert status == 421, tresc
    assert json.loads(tresc) == {"error": "unknown_host"}
    rollbar_narzedzi.report_exc_info.assert_not_called()
    rollbar_routingu.report_exc_info.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_host_z_prawidlowym_portem_dziala_end_to_end(settings, uczelnia, autor):
    """Kryterium spec §12 („``/mcp`` działa pod Daphne, ``run-site run``").

    Pod Daphne serwer słucha na losowym porcie, więc nagłówek to
    ``localhost:<port>``. Test idzie PRZEZ CAŁY STOS aż do prawdziwego
    ``/api/v1/autor/`` i sprawdza DANE, nie tylko status: przed poprawką
    odpowiedź też miała HTTP 200, tylko z ``isError`` i komunikatem „Host spoza
    bieżącego żądania jest niedozwolony".
    """
    autor.nazwisko = "Nazwiskotestowe"
    autor.save()

    router = _router(settings)
    (_, (status, _, tresc)) = _dialog(router, "bpp.example.test:8000")

    assert status == 200, tresc
    odpowiedz = json.loads(tresc)
    assert "error" not in odpowiedz, odpowiedz
    wynik = odpowiedz["result"]
    assert not wynik.get("isError"), wynik
    dane = json.loads(wynik["content"][0]["text"])
    assert [a["nazwisko"] for a in dane["autorzy"]] == ["Nazwiskotestowe"]


def _dane(host):
    return DaneZadania(
        host=host, scheme="https", ip="198.51.100.9", bearer=None, deadline=None
    )


def _przechwytujacy():
    zebrane = []

    def handler(request):
        zebrane.append(request)
        return httpx.Response(200, json={"ok": 1})

    return httpx.MockTransport(handler), zebrane


def test_obcy_host_nadal_odrzucony_mimo_portu_w_naglowku():
    """Poprawka pkt 2 NIE MOŻE osłabić kontroli z ``test_bezpieczenstwo``.

    Porównujemy teraz domenę z domeną — obcy host w URL-u (np. w polu ``next``
    paginacji) ma dalej lecieć na ``BppError``, także gdy nagłówek ``Host``
    bieżącego żądania niesie port.
    """
    transport, _ = _przechwytujacy()

    async def scenariusz():
        zeton = dane_zadania.set(_dane("bpp.a.test:8000"))
        try:
            klient = BppClientInProcess(transport=transport)
            with pytest.raises(BppError):
                await klient.get_json("https://bpp.zly.test/api/v1/autor/1/")
        finally:
            dane_zadania.reset(zeton)

    uruchom(scenariusz)


def test_wlasny_host_z_portem_przechodzi_w_kliencie():
    """Kontrola pozytywna do testu wyżej — bramka nie może być „odrzuca wszystko"."""
    transport, zebrane = _przechwytujacy()

    async def scenariusz():
        zeton = dane_zadania.set(_dane("bpp.a.test:8000"))
        try:
            klient = BppClientInProcess(transport=transport)
            await klient.get_json("https://bpp.a.test/api/v1/autor/1/")
        finally:
            dane_zadania.reset(zeton)

    uruchom(scenariusz)
    assert zebrane and str(zebrane[0].url).startswith("https://bpp.a.test/api/v1/")
