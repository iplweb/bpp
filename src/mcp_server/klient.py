"""Klient wołający własną aplikację Django w procesie."""

from __future__ import annotations

from mcp_server.kontekst import biezace


class KlientScope:
    """Nadpisuje ``scope["client"]`` prawdziwym IP pytającego.

    ``httpx.ASGITransport`` buduje scope wewnętrznego żądania sam i wpisuje
    tam ``("127.0.0.1", 123)``. Warstwa stojąca PRZED aplikacją MCP nie ma jak
    tego dosięgnąć — to jedyne miejsce, w którym da się to poprawić. Bez tego
    ``SearchAnonThrottle`` (liczy po IP) zlewa wszystkich anonimów do jednego
    kubełka (spec §7.3).
    """

    def __init__(self, aplikacja) -> None:
        self._aplikacja = aplikacja

    async def __call__(self, scope, receive, send):
        dane = biezace()  # fail-closed
        scope = dict(scope)
        scope["client"] = (dane.ip, 0)
        await self._aplikacja(scope, receive, send)
