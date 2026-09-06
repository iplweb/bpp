"""Pełna ścieżka: POST /mcp → initialize → tools/list, bez sieci."""

import pytest

from mcp_server.aplikacja import build_application
from mcp_server.routing import RouterHttp
from mcp_server.tests.utils import uruchom, wywolaj, zbuduj_scope


async def _django(scope, receive, send):
    await send({"type": "http.response.start", "status": 404, "headers": []})
    await send({"type": "http.response.body", "body": b""})


def _router(settings):
    settings.ALLOWED_HOSTS = ["bpp.example.test"]
    mcp_app, start = build_application()
    return RouterHttp(mcp_app, _django, start)


@pytest.mark.django_db(transaction=True)
def test_initialize_zwraca_serverinfo(settings):
    router = _router(settings)
    scope = zbuduj_scope(
        "/mcp",
        naglowki={
            "content-type": "application/json",
            "accept": "application/json, text/event-stream",
        },
    )
    cialo = {
        "jsonrpc": "2.0",
        "id": 1,
        "method": "initialize",
        "params": {
            "protocolVersion": "2025-06-18",
            "capabilities": {},
            "clientInfo": {"name": "test", "version": "0"},
        },
    }
    status, _, tresc = uruchom(lambda: wywolaj(router, scope, cialo))
    assert status == 200
    assert '"serverInfo"' in tresc and '"bpp"' in tresc


@pytest.mark.django_db(transaction=True)
def test_zle_host_daje_421(settings):
    """Ochrona przed DNS-rebinding SDK działa niezależnie od ALLOWED_HOSTS."""
    router = _router(settings)
    scope = zbuduj_scope(
        "/mcp",
        host="zly.host",
        naglowki={"content-type": "application/json"},
    )
    status, _, _ = uruchom(
        lambda: wywolaj(router, scope, {"jsonrpc": "2.0", "id": 1, "method": "ping"})
    )
    assert status in (403, 421)
