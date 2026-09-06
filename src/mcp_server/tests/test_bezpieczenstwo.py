"""Regresje bezpieczeństwa warstwy /mcp (spec §7)."""

import httpx
import pytest
from bpp_mcp.client import BppError

from mcp_server.klient import BppClientInProcess
from mcp_server.kontekst import DaneZadania, dane_zadania
from mcp_server.tests.utils import uruchom


def _dane(host="bpp.example.test", bearer=None):
    return DaneZadania(
        host=host, scheme="https", ip="198.51.100.9", bearer=bearer, deadline=None
    )


def _przechwytujacy():
    zebrane = []

    def handler(request):
        zebrane.append(request)
        return httpx.Response(200, json={"ok": 1})

    return httpx.MockTransport(handler), zebrane


def test_cookie_nie_trafia_do_zadania_wewnetrznego():
    """Cookie uwierzytelniłoby sesją przez SessionAuthentication — z pełnymi
    uprawnieniami, bez zgody, bez scope i bez revoke (spec §7.1)."""
    transport, zebrane = _przechwytujacy()

    async def scenariusz():
        zeton = dane_zadania.set(_dane())
        try:
            klient = BppClientInProcess(transport=transport)
            await klient.get_json("autor/1/")
        finally:
            dane_zadania.reset(zeton)

    uruchom(scenariusz)
    assert "cookie" not in {k.lower() for k in zebrane[0].headers}


def test_basic_nie_trafia_do_zadania_wewnetrznego():
    """BasicAuthentication jest trzecia w DEFAULT_AUTHENTICATION_CLASSES,
    a ApiReadOnlyForBearerMiddleware sprawdza tylko prefiks 'bearer ', więc
    dla Basica warstwa read-only NIE istnieje (spec §7.1)."""
    transport, zebrane = _przechwytujacy()

    async def scenariusz():
        zeton = dane_zadania.set(_dane(bearer=None))
        try:
            klient = BppClientInProcess(transport=transport)
            await klient.get_json("autor/1/")
        finally:
            dane_zadania.reset(zeton)

    uruchom(scenariusz)
    naglowek = zebrane[0].headers.get("authorization", "")
    assert not naglowek.lower().startswith("basic")


def test_sciezka_spoza_api_v1_odrzucona():
    transport, _ = _przechwytujacy()

    async def scenariusz():
        zeton = dane_zadania.set(_dane())
        try:
            klient = BppClientInProcess(transport=transport)
            with pytest.raises(BppError):
                await klient.get_json("https://bpp.example.test/admin/")
        finally:
            dane_zadania.reset(zeton)

    uruchom(scenariusz)


def test_obcy_host_w_url_odrzucony():
    """_full_url przyjmuje URL-e bezwzględne wprost, a paginacyjne `next` je
    niosą — kontrola musi obejmować host, nie tylko prefiks (spec §7.4)."""
    transport, _ = _przechwytujacy()

    async def scenariusz():
        zeton = dane_zadania.set(_dane(host="bpp.a.test"))
        try:
            klient = BppClientInProcess(transport=transport)
            with pytest.raises(BppError):
                await klient.get_json("https://bpp.zly.test/api/v1/autor/1/")
        finally:
            dane_zadania.reset(zeton)

    uruchom(scenariusz)
