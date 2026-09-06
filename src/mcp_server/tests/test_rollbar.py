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
import pytest
from mcp.server.mcpserver.exceptions import UnexpectedToolError

from mcp_server import aplikacja
from mcp_server.aplikacja import build_application
from mcp_server.tests.utils import uruchom


async def _wybuchaj(*_a, **_kw):
    raise RuntimeError("awaria-testowa-narzedzia")


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
