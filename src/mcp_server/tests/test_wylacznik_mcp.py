"""Wyłącznik serwera MCP na obiekcie ``Uczelnia`` — niezależny od REST API.

``api_v1_wlaczone=False`` gasi MCP tylko pośrednio: klient łączy się, widzi
listę narzędzi i dostaje błąd przy każdym wywołaniu, a przy okazji odcina
wszystkie integracje ``/api/v1/``. ``mcp_wlaczone`` wyłącza sam MCP — adresy
``/mcp`` i ``/mcp/auth``, dokument PRM i instrukcję na stronie ``/mcp/``.
"""

from contextlib import asynccontextmanager

import pytest
from asgiref.sync import sync_to_async

from bpp.admin.uczelnia import UczelniaAdmin
from mcp_server.routing import RouterHttp
from mcp_server.start import StartMcp
from mcp_server.tests.utils import uruchom, wywolaj, zbuduj_scope

PRM = "/.well-known/oauth-protected-resource"


class _AtrapaLifespanu:
    def __init__(self):
        self.router = self

    def lifespan_context(self, _app):
        @asynccontextmanager
        async def _ctx():
            yield

        return _ctx()


async def _mcp(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"MCP"})


async def _django(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"DJANGO"})


def _router():
    return RouterHttp(_mcp, _django, StartMcp(_AtrapaLifespanu()))


def _odpytaj(host, sciezka="/mcp", router=None):
    router = router or _router()
    return uruchom(lambda: wywolaj(router, zbuduj_scope(sciezka, host=host)))


def _wylacz(uczelnia):
    uczelnia.mcp_wlaczone = False
    uczelnia.save(update_fields=["mcp_wlaczone"])


def test_domyslnie_mcp_wlaczone(uczelnia):
    """Wdrożenie sprzed tej zmiany nie traci MCP po migracji."""
    assert uczelnia.mcp_wlaczone is True


@pytest.mark.django_db(transaction=True)
def test_wylaczone_mcp_zwraca_404(uczelnia):
    _wylacz(uczelnia)

    status, _, tresc = _odpytaj("bpp.example.test")

    assert status == 404
    assert "MCP" not in tresc
    assert "mcp_disabled" in tresc


@pytest.mark.django_db(transaction=True)
def test_wylaczone_mcp_auth_zwraca_404_zamiast_401(uczelnia):
    """401 z ``WWW-Authenticate`` uruchomiłoby w kliencie logowanie OAuth do
    usługi, której nie ma — wyłącznik musi rozstrzygać PRZED bramką bearera."""
    _wylacz(uczelnia)

    status, naglowki, _ = _odpytaj("bpp.example.test", "/mcp/auth")

    assert status == 404
    assert "www-authenticate" not in naglowki


@pytest.mark.django_db(transaction=True)
def test_wylaczenie_dotyczy_tylko_swojej_uczelni(uczelnia1, uczelnia2):
    _wylacz(uczelnia1)

    assert _odpytaj("uczelnia1.localhost")[0] == 404
    status, _, tresc = _odpytaj("uczelnia2.localhost")
    assert status == 200 and tresc == "MCP"


@pytest.mark.django_db(transaction=True)
def test_wylaczenie_dziala_bez_restartu_procesu(uczelnia):
    """Flaga jest czytana per żądanie, nie zapiekana przy budowie routera.

    Oba żądania w JEDNEJ pętli: menedżer sesji MCP (``StartMcp``) wiąże się
    z pętlą, na której wystartował, a każde ``uruchom`` stawia nową — drugie
    wywołanie dostałoby 503 z powodu testu, nie wyłącznika.
    """
    router = _router()

    async def scenariusz():
        przed, _, _ = await wywolaj(router, zbuduj_scope("/mcp"))
        await sync_to_async(_wylacz, thread_sensitive=False)(uczelnia)
        po, _, _ = await wywolaj(router, zbuduj_scope("/mcp"))
        return przed, po

    assert uruchom(scenariusz) == (200, 404)


@pytest.mark.django_db(transaction=True)
def test_wylaczone_mcp_nie_rusza_rest_api(uczelnia, client, settings):
    """To jest cały sens osobnego pola: integracje ``/api/v1/`` działają."""
    settings.ALLOWED_HOSTS = ["bpp.example.test"]
    _wylacz(uczelnia)

    odp = client.get("/api/v1/", HTTP_HOST="bpp.example.test")

    assert odp.status_code == 200


@pytest.mark.django_db
def test_strona_mcp_przy_wylaczonym_nie_pokazuje_adresow(uczelnia, client, settings):
    settings.ALLOWED_HOSTS = ["bpp.example.test"]
    _wylacz(uczelnia)

    odp = client.get("/mcp/", HTTP_HOST="bpp.example.test")

    assert odp.status_code == 404
    tresc = odp.content.decode()
    assert "wyłączony" in tresc
    # Nie gołe „bpp.example.test/mcp" — base.html ma ``og:url`` z adresem
    # bieżącej strony (``/mcp/``). Sprawdzamy to, co widzi człowiek: adresy.
    assert "<code>http://bpp.example.test/mcp" not in tresc
    assert "/mcp/auth" not in tresc


@pytest.mark.django_db
def test_prm_przy_wylaczonym_mcp_zwraca_404(uczelnia, client, settings):
    """PRM opisuje zasób ``/mcp`` — przy wyłączonym MCP nie ma czego opisywać,
    a klient nie powinien dostać wskazówki, gdzie się logować."""
    settings.ALLOWED_HOSTS = ["bpp.example.test"]
    _wylacz(uczelnia)

    odp = client.get(PRM, HTTP_HOST="bpp.example.test")

    assert odp.status_code == 404


@pytest.mark.django_db
def test_prm_przy_wlaczonym_mcp_dziala(uczelnia, client, settings):
    settings.ALLOWED_HOSTS = ["bpp.example.test"]

    odp = client.get(PRM, HTTP_HOST="bpp.example.test")

    assert odp.status_code == 200


def test_admin_uczelni_ma_przelacznik_mcp_w_osobnym_fieldsecie():
    """Osobny fieldset, nie dopisek do „REST API" — inaczej redaktor uzna, że
    wyłączenie API wyłącza też MCP i odwrotnie."""
    for nazwa, opcje in UczelniaAdmin.fieldsets:
        if "mcp_wlaczone" in opcje["fields"]:
            assert "api_v1_wlaczone" not in opcje["fields"]
            assert "MCP" in nazwa
            break
    else:
        pytest.fail("Pole mcp_wlaczone nie jest widoczne w adminie uczelni")
