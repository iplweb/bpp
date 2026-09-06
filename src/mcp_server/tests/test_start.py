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
    """Namiastka aplikacji Starlette: liczy wejścia w lifespan.

    ``lifespan_context`` otwiera PRAWDZIWĄ ``anyio.create_task_group()`` —
    tak jak realnie robi to ``session_manager.run()`` z SDK MCP. Bez tego
    atrapa nie odwzorowuje mechanizmu z BL-3: prosty ``@asynccontextmanager``
    bez grupy zadań nie zostawia na stosie zadania żadnego cancel scope'u,
    więc naiwna (błędna) implementacja ``StartMcp`` nie psuje się przez
    ``RuntimeError`` opisany w docstringu ``start.py`` — tylko wisi, aż
    zewnętrzny ``fail_after`` ubije ją po timeout (inny, dużo wolniejszy
    i mniej precyzyjny sposób zawodzenia testu).
    """

    def __init__(self, blad=None):
        self.wejscia = 0
        self._blad = blad
        self.router = self

    @asynccontextmanager
    async def lifespan_context(self, _app):
        if self._blad is not None:
            raise self._blad
        self.wejscia += 1
        async with anyio.create_task_group():
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


def test_wiele_rownoleglych_zapewnij_wchodzi_raz():
    """Brak punktu przerwania między ``if self._zadanie is None`` a
    ``create_task`` (komentarz w ``start.py``) ma znaczenie tylko wtedy, gdy
    wiele wywołań ``zapewnij()`` rusza NAPRAWDĘ współbieżnie w tej samej
    pętli — sekwencyjne `await` (jak w testach wyżej) tego nie sprawdza.
    Tu odpalamy 50 wywołań przez ``asyncio.gather`` na raz."""
    app = _AplikacjaZLifespanem()
    start = StartMcp(app)

    async def scenariusz():
        await asyncio.gather(*(start.zapewnij() for _ in range(50)))
        return app.wejscia

    assert uruchom(scenariusz) == 1
