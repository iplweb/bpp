"""Routing ASGI: rozdział /mcp od reszty serwisu oraz obsługa lifespanu."""

from __future__ import annotations

import time

from bpp_mcp.auth import set_current_bearer
from django.conf import settings

from django_bpp.client_ip import get_client_ip
from mcp_server.auth import BramkaBearera
from mcp_server.kontekst import DaneZadania, dane_zadania
from mcp_server.start import StartMcp

#: Budżet czasu jednego wywołania narzędzia (spec D11).
BUDZET_SEKUND = getattr(settings, "MCP_BUDZET_SEKUND", 25.0)

SCIEZKA_PUBLICZNA = "/mcp"
SCIEZKA_Z_LOGOWANIEM = "/mcp/auth"


class LifespanMcp:
    """Obsługuje scope ``lifespan``, którego ProtocolTypeRouter nie zna.

    Klucza ``"lifespan"`` po prostu nie ma dziś w mapie routera, więc uvicorn
    dostaje ValueError, loguje „lifespan appears unsupported" i jedzie dalej —
    a menedżer sesji MCP nigdy nie wstaje (spec §2.4).
    """

    def __init__(self, start: StartMcp) -> None:
        self._start = start

    async def __call__(self, scope, receive, send):
        while True:
            komunikat = await receive()
            if komunikat["type"] == "lifespan.startup":
                try:
                    await self._start.zapewnij()
                except Exception as exc:
                    # Świadomie NIE połykamy: pod gunicornem worker padnie
                    # i zostanie respawnowany, czyli awaria będzie widoczna
                    # jako boot-loop, a nie jako cisza (spec §5.1).
                    await send({"type": "lifespan.startup.failed", "message": str(exc)})
                    return
                await send({"type": "lifespan.startup.complete"})
            elif komunikat["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return


class RouterHttp:
    """Kieruje ``/mcp`` i ``/mcp/auth`` do MCP, resztę do Django."""

    def __init__(self, mcp_app, django_app, start: StartMcp) -> None:
        self._django = django_app
        self._start = start
        self._publiczny = BramkaBearera(mcp_app, wymagany=False)
        self._z_logowaniem = BramkaBearera(mcp_app, wymagany=True)

    async def __call__(self, scope, receive, send):
        sciezka = scope.get("path", "")
        if sciezka not in (SCIEZKA_PUBLICZNA, SCIEZKA_Z_LOGOWANIEM):
            await self._django(scope, receive, send)
            return

        if scope.get("method") == "GET" and self._chce_html(scope):
            await self._przekieruj(send, "/mcp/")
            return

        # PIERWSZA instrukcja i POZA jakimkolwiek cancel scope'em (spec §5.1).
        await self._start.zapewnij()
        if not self._start.zywy:
            await self._niedostepny(send)
            return

        dane = self._dane(scope)
        zeton = dane_zadania.set(dane)
        # DWA ContextVary, nie jeden. `BppClient._auth_kwargs` czyta token
        # z WŁASNEGO ContextVara pakietu bpp_mcp (`bpp_mcp.auth`), nie
        # z naszego. Bez tej linii `DaneZadania.bearer` nie ma żadnej drogi
        # do żądania wychodzącego i KAŻDE wywołanie leci anonimowo — czyli
        # zalogowany użytkownik po cichu traci dostęp do swoich danych,
        # a cała warstwa OAuth staje się dekoracją.
        set_current_bearer(dane.bearer)
        try:
            if sciezka == SCIEZKA_Z_LOGOWANIEM:
                # SDK montuje trasę jako Route (^/mcp$), nie Mount — bez
                # przepisania drugi adres dostałby 404 (spec §5.1, BL-1).
                scope = dict(scope, path=SCIEZKA_PUBLICZNA, raw_path=b"/mcp")
                await self._z_logowaniem(scope, receive, send)
            else:
                await self._publiczny(scope, receive, send)
        finally:
            dane_zadania.reset(zeton)
            # set_current_bearer nie zwraca tokenu resetu, więc czyścimy
            # jawnie — inaczej token wyciekłby do następnego żądania
            # obsłużonego w tym samym kontekście.
            set_current_bearer(None)

    @staticmethod
    def _chce_html(scope) -> bool:
        for klucz, wartosc in scope.get("headers", []):
            if klucz.lower() == b"accept" and b"text/html" in wartosc.lower():
                return True
        return False

    @staticmethod
    def _dane(scope) -> DaneZadania:
        # UWAGA: klucze ASGI to bajty — bez ``.decode()`` na kluczu każde
        # `naglowki.get("host", …)` z napisowym kluczem chybia (bajty != str)
        # i ZAWSZE trafia w wartość domyślną. Skutek po cichu: bearer
        # zawsze None, host zawsze "localhost" — mostek z pkt 2 briefu
        # wygląda podłączony, a nic nie przenosi.
        naglowki = {k.lower().decode(): v.decode() for k, v in scope.get("headers", [])}
        host = naglowki.get("host", "localhost")
        # nginx→uvicorn jest plaintext; prawdziwy schemat niesie
        # X-Forwarded-Proto (spec §7.6). Nagłówka NIE przekazujemy dalej —
        # służy wyłącznie do zbudowania adresu bazowego.
        scheme = naglowki.get("x-forwarded-proto", scope.get("scheme", "http"))
        bearer = None
        surowy = naglowki.get("authorization", "")
        if surowy.lower().startswith("bearer "):
            bearer = surowy.split(" ", 1)[1].strip()
        return DaneZadania(
            host=host,
            scheme="https" if scheme == "https" else "http",
            ip=get_client_ip(_UdajeRequest(scope, naglowki)),
            bearer=bearer,
            deadline=time.monotonic() + BUDZET_SEKUND,
        )

    @staticmethod
    async def _przekieruj(send, gdzie: str) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 307,
                "headers": [(b"location", gdzie.encode())],
            }
        )
        await send({"type": "http.response.body", "body": b""})

    @staticmethod
    async def _niedostepny(send) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 503,
                "headers": [(b"content-type", b"application/json")],
            }
        )
        await send(
            {"type": "http.response.body", "body": b'{"error":"mcp_unavailable"}'}
        )


class _UdajeRequest:
    """Minimalny obiekt zgodny z tym, czego oczekuje ``get_client_ip``."""

    def __init__(self, scope, naglowki):
        klient = scope.get("client") or ("", 0)
        self.META = {"REMOTE_ADDR": klient[0]}
        xff = naglowki.get("x-forwarded-for")
        if xff:
            self.META["HTTP_X_FORWARDED_FOR"] = xff
