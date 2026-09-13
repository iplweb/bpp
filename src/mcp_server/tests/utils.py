"""Pomocniki testowe warstwy ASGI.

Repo nie ma ``pytest-asyncio``, a ``async_to_sync`` rzuca, gdy w bieżącym
wątku biegnie już pętla (flaky zależny od kolejności testów — patrz
``django_bpp/tests/test_asgi_notifications.py``). Odpalamy więc każdą korutynę
w dedykowanym wątku, na świeżej, WŁASNORĘCZNIE zbudowanej pętli.

Dlaczego nie ``asyncio.run``
---------------------------

``channels_broadcast.core.force_sync`` woła ``nest_asyncio.apply()``, gdy trafi
na działającą pętlę zdarzeń. To łatka GLOBALNA I NIEODWRACALNA dla całego
procesu — wystarczy, że wykona się raz, w dowolnym teście, i obowiązuje do
końca życia workera pytest-xdist. Robi trzy rzeczy, z których każda nas boli:

* podmienia ``asyncio.run`` na wersję biorącą pętlę z polityki zamiast tworzyć
  własną — i nigdy jej nie zamykającą (stąd ``ResourceWarning: unclosed event
  loop``). Nasze „każde wywołanie dostaje świeżą pętlę" przestaje być prawdą;
* łata ``policy.get_event_loop``, więc każda pętla wydana tą drogą też jest
  załatana;
* podmienia ``_run_once`` na wersję wywłaszczającą bieżące zadanie
  (``curr_tasks.pop``), przez co ``asyncio.current_task()`` bywa ``None``.

Na tym ostatnim opiera się przekazywanie sterowania w ``asgiref`` między
``SyncToAsync`` a ``AsyncToSync``. A my przechodzimy przez nie na KAŻDYM
żądaniu ``/api/v1/``, bo ``ApiReadOnlyForBearerMiddleware`` jest synchroniczne
i Django musi je w łańcuchu ASGI zaadaptować. Efekt na CI: wątek roboczy stoi
w ``CurrentThreadExecutor.run_until_future``, wątek pętli stoi w ``select()``,
i shard wisi do limitu joba. Diagnoza: zrzut SIGABRT/faulthandler z sharda 5.

Obrona jest dwuczęściowa, bo łatka atakuje na dwóch poziomach.

``asyncio.Runner`` (3.11+, a ``requires-python`` to ``>=3.11``) nie jest przez
``nest_asyncio`` ruszany i daje semantykę sprzątania ``asyncio.run``: anulowanie
zadań, ``shutdown_asyncgens``, ``shutdown_default_executor``, ``close``.

Sama fabryka pętli nie wystarcza. ``_patch_loop`` robi ``cls =
loop.__class__`` i podmienia metody NA KLASIE, więc ``asyncio.new_event_loop()``
oddaje po zatruciu pętlę równie załataną. Dlatego ``PetlaBezLatki`` przywraca
cztery metody wprost z ``asyncio.BaseEventLoop`` (klasy bazowej łatka nie
dotyka — celuje w konkretną, np. ``_UnixSelectorEventLoop``) i deklaruje
``_nest_patched = True``. Ten marker jest celowy: ``_patch_loop`` zaczyna się
od ``if hasattr(loop, '_nest_patched'): return``, więc późniejsze ``apply()``
ominie naszą klasę zamiast ją zepsuć.
"""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor


class PetlaBezLatki(asyncio.SelectorEventLoop):
    """Pętla ze standardowym sterowaniem, odporna na ``nest_asyncio``."""

    run_forever = asyncio.BaseEventLoop.run_forever
    run_until_complete = asyncio.BaseEventLoop.run_until_complete
    _run_once = asyncio.BaseEventLoop._run_once
    _check_running = asyncio.BaseEventLoop._check_running

    # NIE literówka i nie kopiowanie na ślepo — patrz docstring modułu:
    # to jest wartownik, który powstrzymuje `nest_asyncio._patch_loop`.
    _nest_patched = True


def _na_swiezej_petli(coro_factory):
    with asyncio.Runner(loop_factory=PetlaBezLatki) as runner:
        return runner.run(coro_factory())


def uruchom(coro_factory):
    """Odpal fabrykę korutyn w osobnym wątku i zwróć jej wynik.

    Przyjmujemy FABRYKĘ, nie korutynę: korutyna utworzona w wątku wołającym
    byłaby związana z jego (nieistniejącą) pętlą.
    """
    with ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(_na_swiezej_petli, coro_factory).result()


def zbuduj_scope(sciezka, metoda="POST", host="bpp.example.test", naglowki=None):
    """Minimalny scope HTTP/ASGI do wołania aplikacji wprost."""
    bazowe = [(b"host", host.encode())]
    for k, v in (naglowki or {}).items():
        bazowe.append((k.lower().encode(), v.encode()))
    return {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": metoda,
        "scheme": "http",
        "path": sciezka,
        "raw_path": sciezka.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": bazowe,
        "client": ("203.0.113.7", 54321),
        "server": (host, 80),
    }


async def wywolaj(app, scope, cialo=None):
    """Zawołaj aplikację ASGI i zwróć ``(status, naglowki, tekst)``."""
    raw = json.dumps(cialo).encode() if cialo is not None else b""
    do_odebrania = [{"type": "http.request", "body": raw, "more_body": False}]
    wyslane = []

    async def receive():
        return do_odebrania.pop(0) if do_odebrania else {"type": "http.disconnect"}

    async def send(msg):
        wyslane.append(msg)

    await app(scope, receive, send)
    start = next((m for m in wyslane if m["type"] == "http.response.start"), None)
    tresc = b"".join(
        m.get("body", b"") for m in wyslane if m["type"] == "http.response.body"
    )
    naglowki = {k.decode(): v.decode() for k, v in (start or {}).get("headers", [])}
    return (start or {}).get("status"), naglowki, tresc.decode(errors="replace")
