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
        # 1 s wystarczy: przy poprawnej implementacji test i tak kończy się
        # natychmiast, a przy regresji (zadanie wisi, trzymając grupę) budżet
        # ogranicza karę CI do 1 s zamiast do domyślnych tu 5 s.
        with anyio.fail_after(1):
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


def test_anulowanie_nie_jest_zapamietane_jako_trwaly_blad():
    """``CancelledError`` NIE może latchować stanu.

    ``except BaseException`` łapało też anulowanie, więc JEDNO anulowanie
    z dowolnego powodu (zamykanie procesu, ubita pętla, timeout serwera)
    zapisywało się w ``_blad``. Skutki były dwa i oba złe: ``zapewnij()``
    rzucało wyjątkiem zamiast pozwolić oddać kontrolowane 503, a przy KAŻDYM
    zamknięciu workera szło zgłoszenie do Rollbara — z rutynowego zdarzenia.

    Po poprawce anulowanie zwalnia czekających, nie zostaje zapamiętane
    i nie jest raportowane. Endpoint i tak jest wtedy martwy
    (``zywy is False`` → 503), bo ``session_manager.run()`` SDK wchodzi się
    raz na instancję — świadomie NIE próbujemy restartu (patrz ``zapewnij``).
    """
    from unittest.mock import Mock

    from mcp_server import start as modul_start

    mock_rollbar = Mock()
    app = _AplikacjaZLifespanem()
    start = StartMcp(app)

    async def scenariusz():
        await start.zapewnij()
        start._zadanie.cancel()
        # Dwie tury pętli: jedna na dostarczenie anulowania, druga na
        # domknięcie zadania (``_trzymaj`` ma jeszcze except do wykonania).
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        await start.zapewnij()  # NIE może rzucić — anulowanie to nie awaria
        return start._blad, start.zywy

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(modul_start, "rollbar", mock_rollbar)
        blad, zywy = uruchom(scenariusz)

    assert blad is None, "anulowanie zostało zapamiętane jako trwały błąd"
    assert zywy is False, "po anulowaniu żądania mają dostawać 503"
    mock_rollbar.report_exc_info.assert_not_called()


def test_blad_startu_jest_raportowany_do_rollbara(monkeypatch):
    """Wyjątek host taska nie ma żadnej innej drogi do monitoringu:
    ``CustomRollbarNotifierMiddleware`` łapie wyjątki Django, a ten leci
    w zadaniu tła poza jakimkolwiek żądaniem (spec §7.5). Zgłoszenie idzie
    stąd, a nie z ``RouterHttp``, żeby przypadło RAZ na awarię, a nie raz na
    żądanie — inaczej martwy menedżer sam wyczerpałby kwotę Rollbara."""
    from unittest.mock import Mock

    from mcp_server import start as modul_start

    mock_rollbar = Mock()
    monkeypatch.setattr(modul_start, "rollbar", mock_rollbar)

    app = _AplikacjaZLifespanem(blad=RuntimeError("brak Redisa"))
    start = StartMcp(app)

    async def scenariusz():
        with pytest.raises(RuntimeError):
            await start.zapewnij()
        # drugie i trzecie żądanie NIE mogą dołożyć kolejnych zgłoszeń
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await start.zapewnij()

    uruchom(scenariusz)
    mock_rollbar.report_exc_info.assert_called_once()


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
