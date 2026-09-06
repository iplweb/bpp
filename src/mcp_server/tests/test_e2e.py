"""Pełna ścieżka: POST /mcp → initialize → tools/list → tools/call, bez sieci."""

import json

import pytest

from mcp_server.aplikacja import build_application
from mcp_server.routing import RouterHttp
from mcp_server.tests.utils import uruchom, wywolaj, zbuduj_scope

NAGLOWKI_JSONRPC = {
    "content-type": "application/json",
    # Bez tego SDK odrzuca żądanie w transport_security (klient MCP musi
    # deklarować oba typy, także przy json_response=True).
    "accept": "application/json, text/event-stream",
}


async def _django(scope, receive, send):
    await send({"type": "http.response.start", "status": 404, "headers": []})
    await send({"type": "http.response.body", "body": b""})


def _router(settings, django_app=_django):
    settings.ALLOWED_HOSTS = ["bpp.example.test"]
    mcp_app, start = build_application()
    return RouterHttp(mcp_app, django_app, start)


async def _jsonrpc(router, cialo, host="bpp.example.test"):
    """Jedno żądanie JSON-RPC do ``/mcp``.

    Korutyna, nie funkcja synchroniczna: cały dialog MUSI zmieścić się
    w JEDNEJ pętli zdarzeń. ``uruchom`` zakłada świeżą pętlę per wywołanie,
    a zamknięcie pętli anuluje host task ``StartMcp``, więc kolejne żądanie
    w nowej pętli zastałoby menedżera sesji martwego i dostało 503 — tak jak
    w produkcji po recyklingu workera.
    """
    scope = zbuduj_scope("/mcp", host=host, naglowki=NAGLOWKI_JSONRPC)
    return await wywolaj(router, scope, cialo)


def _wywolaj_jsonrpc(router, cialo, host="bpp.example.test"):
    return uruchom(lambda: _jsonrpc(router, cialo, host))


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


@pytest.mark.django_db(transaction=True)
def test_initialize_zwraca_serverinfo(settings, uczelnia):
    router = _router(settings)
    status, _, tresc = _wywolaj_jsonrpc(router, INITIALIZE)
    assert status == 200
    assert '"serverInfo"' in tresc and '"bpp"' in tresc


def _wynik_narzedzia(tresc: str) -> dict:
    """Wyłuskaj wynik narzędzia z odpowiedzi JSON-RPC.

    SDK pakuje go dwukrotnie: JSON-RPC → ``result.content[0].text`` → JSON
    zwrócony przez narzędzie. Asercja na sam surowy tekst odpowiedzi
    przeszłaby też wtedy, gdyby nazwisko trafiło tam jako echo argumentu,
    więc rozpakowujemy i patrzymy na DANE.
    """
    odpowiedz = json.loads(tresc)
    assert "error" not in odpowiedz, odpowiedz
    wynik = odpowiedz["result"]
    assert not wynik.get("isError"), wynik
    return json.loads(wynik["content"][0]["text"])


@pytest.mark.django_db(transaction=True)
def test_initialize_tools_list_tools_call_przez_pelny_stos(settings, uczelnia, autor):
    """Kryterium spec §12: ``initialize`` → ``tools/list`` → ``tools/call``
    zwracające dane publiczne identyczne z ``/api/v1/``.

    To jest ścieżka, która jest SENSEM tej zmiany, a nie miała żadnej
    regresji — plik sprawdzał wyłącznie ``initialize``. Wywołanie idzie przez
    ``RouterHttp`` → bramkę bearera → aplikację MCP → narzędzie → klienta
    w procesie → prawdziwe ``/api/v1/autor/`` w Django. Bez sieci, ale przez
    KOMPLET warstw: gdyby którakolwiek z nich (kontekst żądania, mostek
    bearera, ``KlientScope``, allowlista ścieżek) przestała działać, ten test
    to zobaczy.
    """
    autor.nazwisko = "Nazwiskotestowe"
    autor.save()

    router = _router(settings)

    async def dialog():
        wyniki = [await _jsonrpc(router, INITIALIZE)]
        wyniki.append(
            await _jsonrpc(router, {"jsonrpc": "2.0", "id": 2, "method": "tools/list"})
        )
        wyniki.append(
            await _jsonrpc(
                router,
                {
                    "jsonrpc": "2.0",
                    "id": 3,
                    "method": "tools/call",
                    "params": {
                        "name": "szukaj_autora",
                        "arguments": {"nazwisko": "Nazwiskotestowe"},
                    },
                },
            )
        )
        return wyniki

    (init, lista, wywolanie) = uruchom(dialog)

    assert init[0] == 200, init
    assert lista[0] == 200, lista
    nazwy = {n["name"] for n in json.loads(lista[2])["result"]["tools"]}
    assert "szukaj_autora" in nazwy

    status, _, tresc = wywolanie
    assert status == 200, tresc
    dane = _wynik_narzedzia(tresc)
    assert dane["laczna_liczba"] == 1, dane
    assert [a["nazwisko"] for a in dane["autorzy"]] == ["Nazwiskotestowe"]


@pytest.mark.django_db(transaction=True)
def test_zle_host_daje_421(settings, uczelnia):
    """Ochrona przed DNS-rebinding SDK działa niezależnie od ALLOWED_HOSTS.

    Host MUSI mieć swój ``Site`` — fixture ``uczelnia`` wiąże go z domeną
    "testserver" (``src/fixtures/conftest_models.py``) — inaczej 421 zapada
    w NASZEJ bramce uczelni (``mcp_server.uczelnia``, patrz
    ``test_bramka_uczelni.py``), zanim żądanie w ogóle dojdzie do SDK, i test
    niczego nie dowodzi o warstwie, którą deklaruje sprawdzać (zweryfikowane:
    bez tej fixture baza jest pusta, więc 421 zapadał u nas — przy wyłączonej
    ochronie SDK, ``_dozwolone_hosty() == []``, cała reszta suity
    ``mcp_server`` była zielona, więc NIC nie pokrywało sprawdzenia hosta
    przez SDK na żywym żądaniu). "testserver" jest jednak SPOZA
    ``ALLOWED_HOSTS`` (``_router`` ustawia je na ``["bpp.example.test"]``),
    więc odrzucenie musi przyjść z ``TransportSecuritySettings`` SDK.
    """
    router = _router(settings)
    scope = zbuduj_scope(
        "/mcp",
        host="testserver",
        naglowki={"content-type": "application/json"},
    )
    status, _, _ = uruchom(
        lambda: wywolaj(router, scope, {"jsonrpc": "2.0", "id": 1, "method": "ping"})
    )
    assert status in (403, 421)
