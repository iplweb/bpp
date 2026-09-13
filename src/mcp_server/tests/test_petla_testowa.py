"""``uruchom()`` musi przeżyć globalną łatkę ``nest_asyncio``.

Bloker, który to wymusił: shard 5 na CI wisiał do 25-minutowego limitu joba,
dwa razy pod rząd, a lokalnie przechodził przy każdej liczbie workerów i nawet
w kontenerze identycznym z CI. Zrzut SIGABRT/faulthandler pokazał zakleszczenie:

* wątek roboczy: ``SyncToAsync`` -> ``ApiReadOnlyForBearerMiddleware`` ->
  ``AsyncToSync`` -> ``CurrentThreadExecutor.run_until_future`` (czeka),
* wątek pętli: ``nest_asyncio._run_once`` -> ``select()`` (nie budzi tamtego).

Źródło łatki to ``channels_broadcast.core.force_sync``, które woła
``nest_asyncio.apply()``, gdy trafi na działającą pętlę. Łatka jest globalna
i nieodwracalna dla procesu, więc wystarczyło, że JAKIKOLWIEK wcześniejszy test
w tym samym workerze xdista ją odpalił. Stąd zależność od rozkładu testów na
workery — czyli nieodtwarzalność lokalnie.

Test niżej pilnuje własności STRUKTURALNEJ: pętla pod ``uruchom()`` ma
standardowe ``_run_once``. Sprawdzone mutacyjnie — pada po przywróceniu
``asyncio.run`` i po samej zamianie fabryki na ``asyncio.new_event_loop``.

Świadomie NIE ma tu testu integracyjnego odtwarzającego samo zakleszczenie.
Próbowałem: minimalny przeskok ``sync_to_async`` -> ``async_to_sync``, także
powtórzony, przechodzi RÓWNIEŻ na zepsutej wersji — byłby zielony z
niewłaściwego powodu. Zakleszczenie wymaga stanu, którego nie da się tanio
odtworzyć w jednym teście (pełny łańcuch middleware Django plus wcześniejsze
testy w tym samym workerze). Dowodem integracyjnym jest cała grupa shardu:

    # wtyczka wołająca `nest_asyncio.apply()` na starcie sesji
    uv run pytest -p nestplug -n 2 --splits 12 --group 6 \
        --splitting-algorithm least_duration --durations-path .test_durations

Bez poprawki wisi (mierzone: >20 min przy normalnych ~55 s), z poprawką
przechodzi.
"""

import asyncio

import pytest

from mcp_server.tests.utils import uruchom


def _zamroz_asyncio(monkeypatch):
    """Zapamiętaj stan, który ``nest_asyncio.apply()`` nadpisuje.

    ``monkeypatch.setattr(obj, nazwa, obecna_wartość)`` zapisuje wartość
    sprzed podmiany i odtwarza ją w teardownie — ustawienie atrybutu na jego
    własną bieżącą wartość jest więc no-opem teraz, a gwarancją przywrócenia
    potem. Bez tego test zatruwałby workera dokładnie tak, jak robi to
    ``channels_broadcast`` — czyli reprodukowałby chorobę zamiast jej pilnować.
    """
    import asyncio.events as events
    import asyncio.futures as futures
    import asyncio.tasks as tasks

    for modul, nazwy in (
        (asyncio, ("run", "Task", "Future", "get_event_loop")),
        (tasks, ("Task", "_CTask")),
        (futures, ("Future", "_CFuture")),
        (events, ("get_event_loop", "_get_event_loop")),
    ):
        for nazwa in nazwy:
            # Atrybut nieistniejący (np. `events._get_event_loop`, usunięte
            # w 3.13 — `nest_asyncio` dopiero je TWORZY) monkeypatch zapamięta
            # jako `notset` i w teardownie USUNIE, zamiast przywracać wartość.
            monkeypatch.setattr(
                modul, nazwa, getattr(modul, nazwa, None), raising=False
            )

    polityka = events.get_event_loop_policy()
    monkeypatch.setattr(
        type(polityka),
        "get_event_loop",
        type(polityka).get_event_loop,
        raising=False,
    )
    monkeypatch.delattr(asyncio, "_nest_patched", raising=False)


def _zatruj_jak_channels_broadcast():
    """Dokładnie to, co robi ``channels_broadcast.core.force_sync:50-54``."""
    nest_asyncio = pytest.importorskip("nest_asyncio")

    petla = asyncio.new_event_loop()
    try:
        nest_asyncio.apply(petla)
    finally:
        petla.close()
    assert getattr(asyncio, "_nest_patched", False), "łatka się nie założyła"


def test_uruchom_biegnie_na_petli_ze_standardowym_sterowaniem(monkeypatch):
    """Warstwa pierwsza: czy pętla ma STANDARDOWE ``_run_once``.

    Asercja celuje w metodę, nie w marker ``_nest_patched`` — ``PetlaBezLatki``
    deklaruje ten marker CELOWO, żeby powstrzymać ``_patch_loop`` (patrz
    docstring ``mcp_server.tests.utils``), więc byłby bezużyteczny jako miara.

    Sam wybór fabryki pętli tu nie wystarcza i test to pilnuje: ``_patch_loop``
    podmienia metody na KLASIE (``cls = loop.__class__``), więc po zatruciu
    także ``asyncio.new_event_loop()`` oddaje pętlę z ``_run_once`` z
    ``nest_asyncio``. Sprawdzone: na wariancie z ``loop_factory=
    asyncio.new_event_loop`` ten test pada.
    """
    _zamroz_asyncio(monkeypatch)
    _zatruj_jak_channels_broadcast()

    async def czyje_run_once():
        petla = asyncio.get_running_loop()
        return type(petla)._run_once is asyncio.BaseEventLoop._run_once

    assert uruchom(czyje_run_once) is True
