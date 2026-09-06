"""Budowa aplikacji MCP: serwer SDK + narzędzia z bpp-mcp + polityka hostów."""

from __future__ import annotations

from contextlib import asynccontextmanager

from bpp_mcp import register_tools
from django.conf import settings
from mcp.server.mcpserver import MCPServer
from mcp.server.transport_security import TransportSecuritySettings

from mcp_server.klient import zbuduj_klienta
from mcp_server.start import StartMcp


class KontekstZadania:
    """Kontrakt lifespanu ``register_tools``, ale klient jest PER ŻĄDANIE.

    ``register_tools`` dokumentuje, że lifespan ma oddać ``KontekstApp`` *albo
    obiekt o tych samych atrybutach*. Korzystamy z tej furtki: ``client`` jest
    property, więc wrappery narzędzi — które czytają go przy każdym wywołaniu —
    dostają klienta zbudowanego dla bieżącego żądania (spec D9).
    """

    #: Host wielo-użytkownikowy: token jednej osoby nie może trafić do żądania
    #: innej, więc NIGDY nie sięgamy do lokalnego cache tokenów.
    bearer_provider = None

    @property
    def client(self):
        return zbuduj_klienta()


def _dozwolone_hosty() -> list[str]:
    """Przetłumacz ``ALLOWED_HOSTS`` na semantykę SDK.

    SDK dopasowuje host dokładnie albo wzorcem ``host:*`` — Django-owe
    ``.domena`` i ``*`` nie działają (spec §6.1). ``*`` w ALLOWED_HOSTS
    (używane w testach) mapujemy na wyłączenie sprawdzania, bo nie ma dla
    niego odpowiednika.
    """
    hosty: list[str] = []
    for wpis in settings.ALLOWED_HOSTS:
        if wpis == "*":
            return []
        hosty.append(wpis.lstrip("."))
        hosty.append(f"{wpis.lstrip('.')}:*")
    return hosty


def build_application():
    """Zbuduj aplikację ASGI serwera MCP i jej ``StartMcp``.

    FABRYKA, nie moduł: allowlista hostów jest liczona z ``settings``, więc
    zbudowanie aplikacji przy imporcie uniemożliwiłoby testom nadpisanie
    ``ALLOWED_HOSTS`` (spec §11).
    """

    @asynccontextmanager
    async def lifespan(_serwer):
        yield KontekstZadania()

    serwer = MCPServer("bpp", version="1", lifespan=lifespan)
    register_tools(serwer)

    hosty = _dozwolone_hosty()
    bezpieczenstwo = TransportSecuritySettings(
        enable_dns_rebinding_protection=bool(hosty),
        allowed_hosts=hosty,
        allowed_origins=[f"https://{h}" for h in hosty if not h.endswith(":*")],
    )

    aplikacja = serwer.streamable_http_app(
        streamable_http_path="/mcp",
        # Bezstanowo: recykling workera (--max-requests) zabiłby sesję
        # stateful w środku pracy użytkownika. json_response znosi SSE, więc
        # proxy_read_timeout nginksa przestaje być tematem (spec D3).
        stateless_http=True,
        json_response=True,
        transport_security=bezpieczenstwo,
    )
    aplikacja.state.serwer_mcp = serwer
    return aplikacja, StartMcp(aplikacja)
