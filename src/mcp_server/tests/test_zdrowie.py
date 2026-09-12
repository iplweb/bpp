"""Stan endpointu MCP: sonda ``/mcp/status`` i gałąź 503 na ``/mcp``.

Kryterium spec §12 („Healthcheck rozróżnia stan procesu od stanu endpointu
MCP”) było wcześniej niespełnione po OBU stronach: ``stan_mcp()`` nie było
wołane z żadnego miejsca produkcyjnego, a gałąź 503 w ``RouterHttp`` była
nieosiągalna, bo ``zapewnij()`` rzucało, ZANIM wykonanie doszło do sprawdzenia
``self._start.zywy``.

Te testy chodzą po PRAWDZIWYM ``StartMcp`` nad aplikacją z PRAWDZIWĄ
``anyio.create_task_group()`` i zatruwają ją tak, jak robi to awaria produkcyjna
(wyjątek w zadaniu-dziecku anuluje scope grupy). Poprzednia wersja tego pliku
podstawiała atrapę z dwoma atrybutami — przeszłaby przy dowolnej implementacji,
w tym przy takiej, w której sonda nie istnieje.
"""

import asyncio
import json
from contextlib import asynccontextmanager

import anyio

from mcp_server.routing import RouterHttp
from mcp_server.start import StartMcp
from mcp_server.tests.utils import uruchom, wywolaj, zbuduj_scope


class _AplikacjaZGrupaZadan:
    """Namiastka aplikacji Starlette z prawdziwą grupą zadań anyio.

    ``session_manager.run()`` z SDK MCP zakłada dokładnie taką grupę; awaria
    produkcyjna, o którą chodzi (§10.3), to wyjątek jej zadania-dziecka.
    Atrapa musi mieć grupę, bo bez niej nie da się odtworzyć zatrucia.
    """

    def __init__(self) -> None:
        self.router = self
        self._grupa = None

    @asynccontextmanager
    async def lifespan_context(self, _app):
        async with anyio.create_task_group() as grupa:
            self._grupa = grupa
            yield

    def zatruj(self) -> None:
        """Wpuść do grupy dziecko, które rzuca — jak awaria w menedżerze sesji."""

        async def dziecko():
            raise RuntimeError("zatrucie grupy zadań menedżera sesji")

        self._grupa.start_soon(dziecko)


async def _django(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send(
        {"type": "http.response.body", "body": b"DJANGO:" + scope["path"].encode()}
    )


async def _mcp(scope, receive, send):
    await send({"type": "http.response.start", "status": 200, "headers": []})
    await send({"type": "http.response.body", "body": b"MCP"})


def _router(app):
    return RouterHttp(_mcp, _django, StartMcp(app))


def test_status_startuje_menedzera_i_oddaje_200():
    """Świeży worker pod Daphne nie przeszedł protokołu lifespan, więc sonda
    MUSI wyzwolić leniwy start — inaczej raportowałaby „padnięte” na w pełni
    zdrowym procesie.

    Brak ``@pytest.mark.django_db`` jest tu ASERCJĄ, nie zaniedbaniem: sonda
    ma nie dotykać bazy (wymóg z briefu), a pytest-django wywali każdy dostęp
    do ORM w teście bez tego markera.
    """
    app = _AplikacjaZGrupaZadan()
    router = _router(app)
    status, naglowki, tresc = uruchom(
        lambda: wywolaj(router, zbuduj_scope("/mcp/status", metoda="GET"))
    )
    assert status == 200
    assert naglowki["content-type"] == "application/json"
    assert json.loads(tresc) == {"status": "ok", "wystartowany": True, "zywy": True}


def test_status_po_zatruciu_oddaje_503_i_rozroznia_stan():
    """Proces żyje (odpowiada!), a endpoint MCP nie — i sonda to rozróżnia.

    ``wystartowany`` zostaje w treści właśnie po to, żeby odróżnić „jeszcze nie
    wstał” od „wstał i padł”: to drugie znaczy, że czekanie nic nie da i trzeba
    zrecyklingować workera.
    """
    app = _AplikacjaZGrupaZadan()
    router = _router(app)

    async def scenariusz():
        przed = await wywolaj(router, zbuduj_scope("/mcp/status", metoda="GET"))
        app.zatruj()
        await asyncio.sleep(0.05)  # niech dziecko zdąży rzucić i anulować grupę
        po = await wywolaj(router, zbuduj_scope("/mcp/status", metoda="GET"))
        return przed, po

    (status_przed, _, _), (status_po, _, tresc_po) = uruchom(scenariusz)
    assert status_przed == 200
    assert status_po == 503
    assert json.loads(tresc_po) == {
        "status": "error",
        "wystartowany": False,
        "zywy": False,
    }


def test_mcp_po_zatruciu_oddaje_kontrolowane_503():
    """REGRESJA: gałąź 503 ``RouterHttp`` była martwym kodem.

    ``_trzymaj`` zapisuje wyjątek dziecka w ``_blad``, więc ``zapewnij()``
    rzuca RuntimeError ZANIM wykonanie dojdzie do ``if not self._start.zywy``.
    Wyjątek wychodził wtedy poza aplikację ASGI — serwer oddawał gołe 500 bez
    treści i bez śladu w monitoringu. Test mutacyjny: usunięcie ``try/except``
    wokół ``zapewnij()`` w ``_obsluz`` wywala ten test wyjątkiem, nie asercją.
    """
    app = _AplikacjaZGrupaZadan()
    router = _router(app)

    async def scenariusz():
        # Zdrowy start przez sondę, nie przez /mcp: żądanie do /mcp przeszłoby
        # przez bramkę uczelni (baza), a ten test ma sprawdzać wyłącznie
        # kolejność sprawdzeń przy martwym menedżerze — 503 zapada ZANIM
        # bramka uczelni w ogóle zostanie zawołana.
        await wywolaj(router, zbuduj_scope("/mcp/status", metoda="GET"))
        app.zatruj()
        await asyncio.sleep(0.05)
        return await wywolaj(router, zbuduj_scope("/mcp"))

    status, naglowki, tresc = uruchom(scenariusz)
    assert status == 503
    assert json.loads(tresc) == {"error": "mcp_unavailable"}
    assert naglowki["content-type"] == "application/json"


def test_status_nie_idzie_do_django():
    """``/mcp/status`` obsługuje warstwa ASGI — nie Django, więc odpowiada
    także wtedy, gdy stos middleware (kreator, blokada odliczania) po drodze
    przekierowuje albo blokuje."""
    app = _AplikacjaZGrupaZadan()
    status, _, tresc = uruchom(
        lambda: wywolaj(_router(app), zbuduj_scope("/mcp/status", metoda="GET"))
    )
    assert status == 200
    assert "DJANGO" not in tresc
