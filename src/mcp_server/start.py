"""Jednorazowe wejście w lifespan aplikacji MCP, w osobnym zadaniu.

Menedżer sesji MCP zakłada grupę zadań anyio (``session_manager.run()``).
Zadanie, które w nią wchodzi, staje się jej HOST TASKIEM i nigdy z niej nie
wraca (grupa żyje, dopóki host task działa) — a to jest fatalne, gdy tym
zadaniem jest zadanie obsługujące żądanie (spec §5.1). Objaw zależy od tego,
JAK błędnie to zrobiono — nie ma jednego wyjątku do złapania:

* jeśli w tym zadaniu jest aktywny inny cancel scope (nasz budżet czasu)
  i porządek LIFO scope'ów zostanie naruszony, wyjście z tamtego scope'u
  rzuci ``RuntimeError: Attempted to exit a cancel scope that isn't the
  current task's current cancel scope``;
* jeśli zagnieżdżenie scope'ów zostaje poprawne (np. wejście w grupę jest
  w pełni ustrukturyzowane), zadanie żądania po prostu **nigdy nie wraca**
  — wisi, trzymając grupę, aż zewnętrzny budżet czasu (``fail_after``,
  timeout serwera) je anuluje.

W obu przypadkach grupa jest już oznaczona jako wystartowana, więc padają
też WSZYSTKIE kolejne żądania — a anulowanie host taska (timeout,
``application_close_timeout`` Daphne) zatruwa ją nieodwracalnie, bo
``run()`` wchodzi się raz na instancję.

Dlatego host taskiem jest zadanie tła, żyjące tyle, co proces.
"""

from __future__ import annotations

import asyncio


class StartMcp:
    """Trzyma lifespan aplikacji MCP przy życiu przez cały czas życia procesu."""

    def __init__(self, aplikacja) -> None:
        self._aplikacja = aplikacja
        self._gotowe = asyncio.Event()
        self._zadanie: asyncio.Task | None = None
        self._blad: BaseException | None = None

    @property
    def wystartowany(self) -> bool:
        """Czy lifespan został pomyślnie otwarty."""
        return self._gotowe.is_set() and self._blad is None

    @property
    def zywy(self) -> bool:
        """Czy zadanie trzymające grupę nadal działa (healthcheck, spec §10.3)."""
        if self._blad is not None:
            return False
        return self._zadanie is not None and not self._zadanie.done()

    async def zapewnij(self) -> None:
        """Wystartuj menedżera sesji, jeśli jeszcze nie działa, i poczekaj.

        Idempotentne. Wołane z ``LifespanMcp`` (uvicorn) albo z pierwszego
        żądania (Daphne — nie implementuje protokołu lifespan).
        """
        if self._zadanie is None:
            # create_task nie ma punktu przerwania między testem a przypisaniem
            # w tej samej pętli, więc blokada nie jest potrzebna.
            self._zadanie = asyncio.get_running_loop().create_task(self._trzymaj())
        await self._gotowe.wait()
        if self._blad is not None:
            raise RuntimeError("Menedżer sesji MCP nie wstał") from self._blad

    async def _trzymaj(self) -> None:
        """Host task grupy zadań — czeka w nieskończoność."""
        try:
            async with self._aplikacja.router.lifespan_context(self._aplikacja):
                self._gotowe.set()
                await asyncio.Event().wait()
        except BaseException as exc:
            self._blad = exc
            self._gotowe.set()
            raise
