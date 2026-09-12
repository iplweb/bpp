"""Awarie narzędzi MCP muszą trafiać do Rollbara (spec §7.5).

Kontekst: ``MCPServer._handle_call_tool`` (protokołowy handler, wołany
faktycznie przez sesję http) łapie KAŻDY wyjątek narzędzia i zamienia go w
``CallToolResult(is_error=True)`` — dociera do niego jedynie
``logger.exception(...)``, nic z tego nie trafia do warstwy ASGI, więc
``CustomRollbarNotifierMiddleware`` (łapie wyjątki Django) nigdy nie zobaczy
awarii narzędzia. ``_z_raportowaniem`` w ``aplikacja.py`` musi więc zgłosić
wyjątek do Rollbara PRZED tym, jak SDK go pochłonie.

``serwer.call_tool(...)`` (publiczne API ``MCPServer``, użyte tu) NIE łapie
wyjątków — podnosi ``UnexpectedToolError``/``ToolError`` (patrz
``mcp.server.mcpserver.tools.base.Tool.run``). To wystarcza do sprawdzenia
raportowania: nasz wrapper zgłasza wyjątek do Rollbara WCZEŚNIEJ, w środku
opakowanej funkcji narzędzia — zanim jakikolwiek poziom SDK zdąży go złapać
czy przekonwertować.
"""

from unittest.mock import Mock

import bpp_mcp.tools as bpp_tools
import httpx
import pytest
from bpp_mcp.client import BppError
from mcp.server.mcpserver.exceptions import ToolError, UnexpectedToolError

from mcp_server import aplikacja
from mcp_server.aplikacja import build_application
from mcp_server.klient import BppClientInProcess
from mcp_server.kontekst import DaneZadania, dane_zadania
from mcp_server.tests.utils import uruchom


async def _wybuchaj(*_a, **_kw):
    raise RuntimeError("awaria-testowa-narzedzia")


def _rzucajacy_bpperror(status=None):
    async def narzedzie(*_a, **_kw):
        raise BppError("nie znaleziono encji", status_code=status)

    return narzedzie


def _wywolaj_djangoql_schema(monkeypatch, funkcja, oczekiwany_wyjatek):
    """Zbuduj aplikację z podmienionym ``djangoql_schema`` i zawołaj narzędzie.

    ``djangoql_schema`` nie potrzebuje ani ``ctx``, ani klienta HTTP — to
    najlżejsze narzędzie do wywołania bez stawiania pełnego żądania.
    """
    mock_rollbar = Mock()
    monkeypatch.setattr(aplikacja, "rollbar", mock_rollbar)
    monkeypatch.setattr(bpp_tools, "djangoql_schema", funkcja)

    mcp_app, _ = build_application()
    serwer = mcp_app.state.serwer_mcp

    async def scenariusz():
        with pytest.raises(oczekiwany_wyjatek):
            await serwer.call_tool("djangoql_schema", {"model": "rekord"})

    uruchom(scenariusz)
    return mock_rollbar


def test_wyjatek_narzedzia_trafia_do_rollbara(monkeypatch):
    """Wywołanie narzędzia, które rzuca wyjątek, musi zawołać
    ``rollbar.report_exc_info`` — bez tego awarie narzędzi są niewidoczne
    w monitoringu (patrz docstring modułu)."""
    mock_rollbar = Mock()
    monkeypatch.setattr(aplikacja, "rollbar", mock_rollbar)
    # djangoql_schema nie potrzebuje ani ``ctx``, ani klienta HTTP — najlżejsze
    # narzędzie do wywołania bez stawiania pełnego żądania/klienta w procesie.
    monkeypatch.setattr(bpp_tools, "djangoql_schema", _wybuchaj)

    mcp_app, _ = build_application()
    serwer = mcp_app.state.serwer_mcp

    async def scenariusz():
        with pytest.raises(UnexpectedToolError):
            await serwer.call_tool("djangoql_schema", {"model": "rekord"})

    uruchom(scenariusz)

    mock_rollbar.report_exc_info.assert_called_once()


def test_narzedzie_bez_wyjatku_nie_raportuje(monkeypatch):
    """Kontrolny brzeg: powodzenie NIE ma trafiać do Rollbara."""
    mock_rollbar = Mock()
    monkeypatch.setattr(aplikacja, "rollbar", mock_rollbar)

    mcp_app, _ = build_application()
    serwer = mcp_app.state.serwer_mcp

    async def scenariusz():
        return await serwer.call_tool("djangoql_schema", {"model": "rekord"})

    uruchom(scenariusz)

    mock_rollbar.report_exc_info.assert_not_called()


def test_bpperror_nie_trafia_do_rollbara(monkeypatch):
    """``BppError`` to normalny kanał komunikatów do użytkownika, nie awaria.

    Zmierzone przed poprawką: 4 zgłoszenia na 4 wywołania (401 anonima przy
    DjangoQL, dwa 404 nieistniejących encji, walidacja argumentu). Na
    publicznym, nieuwierzytelnionym endpoincie znaczyło to, że dowolna osoba
    z internetu wyczerpuje kwotę Rollbara jednym ``curl``-em w pętli i topi
    realne alerty.
    """
    mock_rollbar = _wywolaj_djangoql_schema(
        monkeypatch, _rzucajacy_bpperror(status=404), ToolError
    )
    mock_rollbar.report_exc_info.assert_not_called()


def test_bpperror_bez_statusu_nie_trafia_do_rollbara(monkeypatch):
    """Błąd domenowy bez statusu HTTP (walidacja argumentu, przekroczony
    budżet czasu) też jest komunikatem, nie awarią."""
    mock_rollbar = _wywolaj_djangoql_schema(
        monkeypatch, _rzucajacy_bpperror(status=None), ToolError
    )
    mock_rollbar.report_exc_info.assert_not_called()


def test_bpperror_5xx_z_prawdziwego_klienta_nie_trafia_do_rollbara(monkeypatch):
    """Regresja na usterkę z self-review PR #804: wcześniejsza wersja
    ``_z_raportowaniem`` robiła wyjątek dla ``BppError`` ze statusem 5xx, z
    uzasadnieniem że taki status mówi o awarii po NASZEJ stronie i „użytkownik
    nie ma jak wymusić 5xx z /api/v1/”. Recenzent zmierzył empirycznie, że jest
    ODWROTNIE: timeout DjangoQL (``statement_timeout`` w
    ``api_v1/viewsets/zapytanie.py``) daje 503 DETERMINISTYCZNIE przy zbyt
    szerokim zapytaniu, a ``retry_5xx=False`` na tej ścieżce
    (w zainstalowanym ``bpp-mcp``) przenosi ten status aż do ``BppError`` —
    3 wywołania dawały 3 zgłoszenia Rollbara, czyli ten sam hałas od anonima,
    który reszta tej funkcji ma wygaszać. Gałąź usunięto całkowicie.

    Test idzie przez PRAWDZIWY ``BppClientInProcess`` (mockowany transport
    HTTP zwracający 503, nie wstrzyknięty wyjątek) — poprzednia wersja tego
    testu wstrzykiwała ``BppError(status_code=503)`` ręcznie prosto do
    narzędzia, co niczego nie dowodziło: klient produkuje taki obiekt
    wyłącznie dla tej jednej, konkretnej ścieżki (DjangoQL), a nie w ogóle
    dla „realnego 500”.

    Wołamy ``narzedzie.fn`` (czyli nasz ``wrapper``) wprost, z ATRAPĄ
    ``Context`` — ``serwer.call_tool()`` (użyte w innych testach tego modułu)
    buduje ``Context`` bez ``request_context``, a ``zapytanie_rekord`` (w
    odróżnieniu od ``djangoql_schema``) go potrzebuje (``_client(ctx)`` w
    zainstalowanym ``bpp-mcp``), więc poleciałby ``ValueError`` niezwiązany
    z tezą tego testu."""
    mock_rollbar = Mock()
    monkeypatch.setattr(aplikacja, "rollbar", mock_rollbar)

    def odpowiedz_503(request):
        return httpx.Response(503, json={"error": "statement_timeout"})

    monkeypatch.setattr(
        aplikacja,
        "zbuduj_klienta",
        lambda: BppClientInProcess(transport=httpx.MockTransport(odpowiedz_503)),
    )

    mcp_app, _ = build_application()
    serwer = mcp_app.state.serwer_mcp
    narzedzie = serwer._tool_manager.get_tool("zapytanie_rekord")

    class _AtrapaRequestContext:
        def __init__(self, lifespan_context):
            self.request = None
            self.lifespan_context = lifespan_context

    class _AtrapaContext:
        def __init__(self, lifespan_context):
            self.request_context = _AtrapaRequestContext(lifespan_context)

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
            ctx = _AtrapaContext(aplikacja.KontekstZadania())
            with pytest.raises(BppError) as exc_info:
                await narzedzie.fn(ctx, "rok=2020")
            assert exc_info.value.status_code == 503
        finally:
            dane_zadania.reset(zeton)

    uruchom(scenariusz)
    mock_rollbar.report_exc_info.assert_not_called()


def test_context_i_schemat_przetrwaly_wrapper():
    """Regresja na ryzyko opisane w docstringu ``_z_raportowaniem``: gdyby
    ``functools.wraps`` nie wystarczał do zachowania sygnatury/adnotacji
    oryginalnej funkcji narzędzia, ``ctx: Context`` przestałby być wykrywany
    jako parametr wstrzykiwany i stałby się (niewykonalnym) polem schematu
    wejściowego — a schemat straciłby prawdziwe parametry narzędzia."""
    mcp_app, _ = build_application()
    serwer = mcp_app.state.serwer_mcp

    narzedzie = serwer._tool_manager.get_tool("szukaj_publikacji")
    assert narzedzie is not None
    assert narzedzie.context_kwarg == "ctx"

    wlasciwosci = narzedzie.parameters["properties"]
    assert "ctx" not in wlasciwosci
    assert set(wlasciwosci) == {"q", "rok_od", "rok_do", "limit"}
    assert narzedzie.parameters["required"] == ["q"]
