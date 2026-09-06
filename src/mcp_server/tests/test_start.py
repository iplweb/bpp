"""StartMcp: wejście w lifespan aplikacji MCP dokładnie raz, w osobnym zadaniu.

Kluczowa regresja (spec §5.1, bloker BL-3): wejście w grupę zadań anyio
z zadania ŻĄDANIA czyni je host taskiem; aktywny w tym zadaniu cancel scope
rzuca wtedy RuntimeError przy wyjściu, a grupa zostaje trwale zepsuta.
"""

import asyncio
from contextlib import asynccontextmanager

import anyio
import pytest

from mcp_server.start import StartMcp
from mcp_server.tests.utils import uruchom


class _AplikacjaZLifespanem:
    """Namiastka aplikacji Starlette: liczy wejścia w lifespan."""

    def __init__(self, blad=None):
        self.wejscia = 0
        self._blad = blad
        self.router = self

    @asynccontextmanager
    async def lifespan_context(self, _app):
        if self._blad is not None:
            raise self._blad
        self.wejscia += 1
        yield


def test_zapewnij_wchodzi_dokladnie_raz():
    app = _AplikacjaZLifespanem()
    start = StartMcp(app)

    async def scenariusz():
        await start.zapewnij()
        await start.zapewnij()
        await start.zapewnij()
        return start.wystartowany

    assert uruchom(scenariusz) is True
    assert app.wejscia == 1


def test_zapewnij_pod_aktywnym_cancel_scope_nie_psuje_zadania():
    """REGRESJA BL-3: wywołanie z zadania, w którym trwa fail_after, nie może
    ani wywalić tego zadania, ani zepsuć kolejnych wywołań."""
    app = _AplikacjaZLifespanem()
    start = StartMcp(app)

    async def scenariusz():
        with anyio.fail_after(5):
            await start.zapewnij()
        # wyjście z fail_after musi się udać — i drugie wywołanie też
        await start.zapewnij()
        return app.wejscia

    assert uruchom(scenariusz) == 1


def test_blad_startu_jest_podnoszony_i_zapamietany():
    app = _AplikacjaZLifespanem(blad=RuntimeError("brak Redisa"))
    start = StartMcp(app)

    async def scenariusz():
        with pytest.raises(RuntimeError):
            await start.zapewnij()
        return start.zywy

    assert uruchom(scenariusz) is False


def test_zadanie_przezywa_zadanie_ktore_je_utworzylo():
    """Grupa zadań ma żyć dłużej niż żądanie, z którego wystartowała."""
    app = _AplikacjaZLifespanem()
    start = StartMcp(app)

    async def scenariusz():
        async def udaje_zadanie():
            await start.zapewnij()

        await asyncio.create_task(udaje_zadanie())
        await asyncio.sleep(0.05)
        return start.zywy

    assert uruchom(scenariusz) is True
