"""KlientScope: wewnętrzne żądanie musi nieść PRAWDZIWE IP pytającego.

httpx.ASGITransport buduje scope sam i wpisuje tam własne ``client``
(127.0.0.1). Bez podmiany wszyscy anonimowi użytkownicy MCP dzieliliby jeden
kubełek throttlingu DRF — jeden klient DoS-owałby wszystkich (spec §7.3).
"""

import time

import httpx
import pytest
from bpp_mcp.client import BppError

from mcp_server.klient import BppClientInProcess, KlientScope, zbuduj_klienta
from mcp_server.kontekst import DaneZadania, dane_zadania
from mcp_server.tests.utils import uruchom


async def _echo_client(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": str(scope["client"]).encode()})


def test_klient_scope_wstawia_ip_z_kontekstu():
    app = KlientScope(_echo_client)

    async def scenariusz():
        zeton = dane_zadania.set(
            DaneZadania(
                host="bpp.example.test",
                scheme="https",
                ip="198.51.100.9",
                bearer=None,
                deadline=None,
            )
        )
        try:
            wyslane = []

            async def send(m):
                wyslane.append(m)

            async def receive():
                return {"type": "http.request", "body": b"", "more_body": False}

            await app({"type": "http", "client": ("127.0.0.1", 123)}, receive, send)
            return b"".join(m.get("body", b"") for m in wyslane).decode()
        finally:
            dane_zadania.reset(zeton)

    assert "198.51.100.9" in uruchom(scenariusz)


def test_klient_scope_bez_kontekstu_rzuca():
    """FAIL-CLOSED: brak kontekstu to błąd programisty, nie powód do cichego
    fallbacku na 127.0.0.1 (spec §5.2)."""
    app = KlientScope(_echo_client)

    async def scenariusz():
        with pytest.raises(RuntimeError):
            await app({"type": "http", "client": ("127.0.0.1", 1)}, None, None)

    uruchom(scenariusz)


def _dane(deadline=None, host="bpp.example.test"):
    return DaneZadania(
        host=host, scheme="https", ip="198.51.100.9", bearer=None, deadline=deadline
    )


def test_api_root_bierze_sie_z_hosta_zadania():
    """Sedno D9: adres API zależy od hosta KONKRETNEGO żądania (spec §5.3)."""

    async def scenariusz():
        zeton = dane_zadania.set(_dane(host="bpp.umlub.pl"))
        try:
            klient = zbuduj_klienta()
            return str(klient._full_url("autor/"))
        finally:
            dane_zadania.reset(zeton)

    assert uruchom(scenariusz) == "https://bpp.umlub.pl/api/v1/autor/"


def test_dwa_zadania_dwa_rozne_adresy():
    async def scenariusz():
        adresy = []
        for host in ("bpp.a.test", "bpp.b.test"):
            zeton = dane_zadania.set(_dane(host=host))
            try:
                adresy.append(str(zbuduj_klienta()._full_url("autor/")))
            finally:
                dane_zadania.reset(zeton)
        return adresy

    a, b = uruchom(scenariusz)
    assert a != b
    assert "bpp.a.test" in a and "bpp.b.test" in b


def test_przekroczony_budzet_zatrzymuje_zadania():
    """REGRESJA BL-2: po wyczerpaniu budżetu klient NIE wykonuje kolejnych
    żądań — limit ma zatrzymywać pracę, nie tylko przestać na nią czekać."""
    wywolania = []

    def handler(request):
        wywolania.append(request)
        return httpx.Response(200, json={"ok": 1})

    async def scenariusz():
        zeton = dane_zadania.set(_dane(deadline=time.monotonic() - 1))
        try:
            klient = BppClientInProcess(transport=httpx.MockTransport(handler))
            # BppError konkretnie, nie goły Exception (ruff B017) — to jest
            # dokładnie ten wyjątek, który _request ma podnieść przy
            # przekroczonym budżecie.
            with pytest.raises(BppError):
                await klient.get_json("autor/1/")
        finally:
            dane_zadania.reset(zeton)

    uruchom(scenariusz)
    assert wywolania == []
