"""Budowa aplikacji MCP: serwer SDK + narzędzia z bpp-mcp + polityka hostów."""

from __future__ import annotations

import functools
from contextlib import asynccontextmanager

import rollbar
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


def _z_raportowaniem(serwer: MCPServer) -> MCPServer:
    """Owiń ``serwer.tool()`` raportowaniem wyjątków narzędzi do Rollbara.

    ``MCPServer._handle_call_tool`` łapie KAŻDY wyjątek handlera i zamienia
    go w ``CallToolResult(is_error=True)`` (patrz
    ``mcp.server.mcpserver.server``) — na tym poziomie zostaje po nim tylko
    ``logger.exception(...)``. Nic z tego nie dociera do warstwy ASGI, więc
    ``CustomRollbarNotifierMiddleware`` (który łapie wyjątki Django) nigdy nie
    zobaczy awarii narzędzia — musimy zgłosić ją sami, ZANIM SDK ją pochłonie
    (spec §7.5).

    Zweryfikowane w zainstalowanym ``mcp`` (2.x), nie zgadywane:

    * ``MCPServer.tool()`` to DEKORATOR-FABRYKA — ``tool(**kw)`` zwraca
      ``decorator``, a ``decorator(fn)`` REJESTRUJE narzędzie natychmiast
      (``self.add_tool(fn, ...)``) i oddaje ``fn`` bez zmian. Rejestracja
      dzieje się więc w momencie dekorowania, nie leniwie — stąd podmiana
      ``serwer.tool`` musi zdążyć PRZED wywołaniem ``register_tools``.
    * Schemat argumentów i wykrycie parametru ``Context`` liczy
      ``Tool.from_function`` na PODANEJ (owinięta) funkcji przez
      ``inspect.signature(fn, eval_str=True)`` i ``typing.get_type_hints(fn)``
      — obie te funkcje stdlib jawnie idą po łańcuchu ``__wrapped__``, więc
      ``functools.wraps`` na wewnętrznym ``wrapper`` wystarcza, by dostały
      oryginalny sygnaturę/adnotacje (i ``__globals__`` oryginału — istotne,
      bo ``bpp_mcp.tools``/``server`` mają ``from __future__ import
      annotations``, więc adnotacja ``Context`` jest stringiem do
      wyliczenia). Potwierdzone w praktyce testem
      ``test_context_i_schemat_przetrwaly_wrapper`` — bez tego wrapper
      zarejestrowałby ``ctx`` jako zwykły, wymagany parametr wejściowy
      zamiast wstrzykiwanego kontekstu.
    """
    oryginalny = serwer.tool

    def tool(*args, **kwargs):
        dekorator = oryginalny(*args, **kwargs)

        def opakuj(fn):
            @functools.wraps(fn)
            async def wrapper(*a, **kw):
                try:
                    return await fn(*a, **kw)
                except Exception:
                    rollbar.report_exc_info()
                    raise

            return dekorator(wrapper)

        return opakuj

    serwer.tool = tool
    return serwer


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
    register_tools(_z_raportowaniem(serwer))

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
