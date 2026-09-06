"""Klient wołający własną aplikację Django w procesie."""

from __future__ import annotations

import time

import httpx
from bpp_mcp.client import BppClient, BppError, TrybAuth
from bpp_mcp.config import Config

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


class BppClientInProcess(BppClient):
    """``BppClient`` wołający własną aplikację Django, bez gniazda TCP.

    Tworzony PER ŻĄDANIE (spec D9): ``BppClient`` zapamiętuje ``api_root``
    w ``__init__``, a adres zależy od nagłówka ``Host`` konkretnego żądania.
    Przy okazji rozwiązuje to izolację cache (świeży klient = świeży słownik)
    i sprowadza semafor do zasięgu jednego wywołania narzędzia.
    """

    def __init__(self, *, transport=None) -> None:
        dane = biezace()
        if transport is None:
            from django_bpp.asgi import django_asgi_app

            transport = httpx.ASGITransport(
                app=KlientScope(django_asgi_app),
                # 500 z aplikacji ma wrócić jako BppNetworkError z czytelnym
                # komunikatem, a nie jako surowy traceback w wyniku narzędzia.
                raise_app_exceptions=False,
            )
        super().__init__(
            Config(base_url=f"{dane.scheme}://{dane.host}", transport="stdio"),
            transport=transport,
            tryb_auth=TrybAuth.W_PROCESIE,
            max_retries=0,  # nie ma sieci, która mogłaby zamigotać
        )
        # Przekierowania WYŁĄCZONE (spec D12): SECURE_SSL_REDIRECT po cichu
        # podwajałby każde żądanie, a FirstRunWizardMiddleware przekierowuje
        # /api/v1/ na HTML kreatora, co kończyłoby się ValueError w resp.json().
        self._client.follow_redirects = False

    async def _request(self, full, *, retry_5xx=True):
        """Egzekwuj budżet czasu PRZED wykonaniem żądania.

        Limit wokół aplikacji MCP nie działa (spec §5.2, BL-2): handler biegnie
        w zadaniu grupy menedżera, więc anulowanie zadania żądania odcina tylko
        odpowiedź. Sprawdzenie musi być tutaj, gdzie faktycznie wykonuje się
        praca.
        """
        dane = biezace()
        if dane.deadline is not None and time.monotonic() >= dane.deadline:
            raise BppError(
                "Przekroczono budżet czasu wywołania narzędzia — zawęź "
                "zapytanie albo poproś o mniej danych."
            )
        if not str(full.path).startswith("/api/v1/"):
            raise BppError(f"Ścieżka spoza /api/v1/ jest niedozwolona: {full.path}")
        if full.host and full.host != dane.host:
            raise BppError(
                f"Host spoza bieżącego żądania jest niedozwolony: {full.host}"
            )
        return await super()._request(full, retry_5xx=retry_5xx)


def zbuduj_klienta() -> BppClientInProcess:
    """Zbuduj klienta dla bieżącego żądania."""
    return BppClientInProcess()
