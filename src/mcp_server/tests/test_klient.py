"""KlientScope: wewnętrzne żądanie musi nieść PRAWDZIWE IP pytającego.

httpx.ASGITransport buduje scope sam i wpisuje tam własne ``client``
(127.0.0.1). Bez podmiany wszyscy anonimowi użytkownicy MCP dzieliliby jeden
kubełek throttlingu DRF — jeden klient DoS-owałby wszystkich (spec §7.3).
"""

import pytest

from mcp_server.klient import KlientScope
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
