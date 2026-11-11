"""Regresja: żądania HTTP przez handler ASGI nie mogą zostawiać połączeń z bazą.

Na produkcji (gunicorn + UvicornWorker, ``CONN_MAX_AGE=0``, pgbouncer w trybie
session) workery trzymały dziesiątki połączeń ``idle`` godzinami — ostatnie
zapytanie każdego to ``SELECT set_config('TimeZone', …)``, czyli połączenie
otwarte i porzucone bez jednego zapytania. Zapychały pulę pgbouncera, a każda
fala ruchu kończyła się ``query_wait_timeout`` („server closed the connection
unexpectedly" w Rollbarze).

Mechanizm: Django trzyma połączenia per wątek (``ConnectionHandler`` jest
``thread_critical``), a ``close_old_connections`` z ``request_finished`` sprząta
tylko wątek żądania. Wszystko, co biegnie przez
``sync_to_async(..., thread_sensitive=False)``, trafia do wątków domyślnego
executora pętli i tam zostawiało połączenia. Dwa źródła:

* globalna łatka w ``bpp/__init__.py`` wymuszała ``thread_sensitive=False``
  wszystkim (easyaudit ``transaction.on_commit``, auth, sesje, axes) —
  usunięta;
* samo Django renderuje odpowiedzi na wyjątki (404/403/500, ``handler404``
  pyta bazę) przez ``sync_to_async(response_for_exception,
  thread_sensitive=False)`` — na to jest ``ZamykajPolaczeniaWPuli``
  (``django_bpp/asgi_polaczenia.py``).

Wątki puli żyją tyle co pętla — po ``asyncio.run`` ginęłyby razem ze swoimi
połączeniami, dlatego liczymy połączenia WEWNĄTRZ pętli, świeżym połączeniem
otwartym specjalnie do pomiaru (jego własny backend jest wykluczony).

Korutynę uruchamiamy w dedykowanym wątku przez ``asyncio.run`` (jak w
``test_asgi_notifications.py``) — odporne na pętlę zostawioną przez inny test.
"""

import asyncio
import gc
import time
from concurrent.futures import ThreadPoolExecutor

import psycopg2
import pytest
from django.core.handlers.asgi import ASGIHandler
from django.db import connection

from django_bpp import asgi
from django_bpp.asgi_polaczenia import ZamykajPolaczeniaWPuli

LICZBA_ZADAN = 30

ZAPYTANIE_LICZACE = (
    "SELECT count(*) FROM pg_stat_activity "
    "WHERE datname = current_database() AND pid <> pg_backend_pid()"
)


def _policz_inne_polaczenia(parametry):
    """Backendy w bieżącej bazie poza tym jednym, otwartym do pomiaru."""
    with psycopg2.connect(**parametry) as pomiar:
        with pomiar.cursor() as kursor:
            kursor.execute(ZAPYTANIE_LICZACE)
            return kursor.fetchone()[0]


def _policz_po_ustabilizowaniu(parametry, limit_s=10.0, krok_s=0.2):
    """Liczba backendów, gdy przestała się zmieniać (dwa równe odczyty z rzędu).

    Połączenia zamknięte po stronie klienta (np. wyciekłe w kontroli, sprzątane
    razem z wątkami zakończonej pętli) PostgreSQL usuwa z ``pg_stat_activity``
    asynchronicznie. Bez czekania pomiar „przed" następnego testu w tym samym
    workerze xdist łapał cudze, właśnie umierające backendy.

    ``gc.collect()``: po śmierci wątku jego ``DatabaseWrapper`` (cykle
    referencji) czeka na garbage collector — dopiero on zamyka gniazdo.
    Bez tego wyciek z testu kontrolnego przeżywał test i kumulował się.
    """
    gc.collect()
    poprzedni = _policz_inne_polaczenia(parametry)
    koniec = time.monotonic() + limit_s
    while time.monotonic() < koniec:
        time.sleep(krok_s)
        biezacy = _policz_inne_polaczenia(parametry)
        if biezacy == poprzedni:
            return biezacy
        poprzedni = biezacy
    raise AssertionError(
        f"Liczba połączeń nie ustabilizowała się w {limit_s} s (ostatnio {poprzedni})"
    )


async def _zadanie_get(aplikacja, sciezka):
    scope = {
        "type": "http",
        "asgi": {"version": "3.0"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": sciezka,
        "raw_path": sciezka.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [(b"host", b"testserver")],
        "client": ("127.0.0.1", 40000),
        "server": ("testserver", 80),
    }
    wyslane = []
    koniec = asyncio.Event()
    do_odebrania = [{"type": "http.request", "body": b"", "more_body": False}]

    async def receive():
        if do_odebrania:
            return do_odebrania.pop(0)
        # Klient nie rozłącza się, dopóki nie dostanie całej odpowiedzi.
        await koniec.wait()
        return {"type": "http.disconnect"}

    async def send(komunikat):
        wyslane.append(komunikat)
        if komunikat["type"] == "http.response.body" and not komunikat.get("more_body"):
            koniec.set()

    await aplikacja(scope, receive, send)
    return wyslane[0]["status"]


def _ruch_i_pomiar(parametry, owin):
    """Równoległe żądania przez ASGI, potem pomiar — wciąż w żywej pętli."""

    async def _run():
        aplikacja = ASGIHandler()
        if owin:
            aplikacja = ZamykajPolaczeniaWPuli(aplikacja)
        przed = await asyncio.to_thread(_policz_po_ustabilizowaniu, parametry)
        statusy = await asyncio.gather(
            *[
                _zadanie_get(aplikacja, f"/bpp/autor/nie-ma-takiego-{i}/")
                for i in range(LICZBA_ZADAN)
            ]
        )
        po = await asyncio.to_thread(_policz_inne_polaczenia, parametry)
        return przed, po, statusy

    with ThreadPoolExecutor(max_workers=1) as wykonawca:
        wynik = wykonawca.submit(asyncio.run, _run()).result()
    # Pętla zamknięta, jej wątki (i ewentualnie wyciekłe połączenia) też —
    # czekamy, aż PostgreSQL je wypuści, żeby nie zaśmiecić kolejnego testu.
    _policz_po_ustabilizowaniu(parametry)
    return wynik


@pytest.mark.django_db(transaction=True)
def test_kontrola_goly_handler_asgi_zostawia_polaczenia_po_404():
    """Kontrola: bez wrappera mechanizm Django naprawdę zostawia połączenia.

    Dowodzi, że test niżej mierzy coś realnego (nie przechodzi „bo i tak
    nic nie wycieka") — i przypina zachowanie Django, przed którym chroni
    wrapper. Gdyby Django kiedyś to naprawiło, ta kontrola zrobi się
    czerwona i będzie sygnałem, że wrapper można zdjąć.
    """
    przed, po, statusy = _ruch_i_pomiar(connection.get_connection_params(), False)

    assert all(s == 404 for s in statusy), statusy
    assert po > przed


@pytest.mark.django_db(transaction=True)
def test_zadania_asgi_nie_zostawiaja_otwartych_polaczen_db():
    przed, po, statusy = _ruch_i_pomiar(connection.get_connection_params(), True)

    # Sanity: żądania przeszły przez cały stos, łącznie z handler404,
    # który pyta bazę (to on zostawiał połączenia).
    assert all(s == 404 for s in statusy), statusy
    assert po == przed, (
        f"Po {LICZBA_ZADAN} żądaniach ASGI zostało {po - przed} otwartych "
        f"połączeń z bazą (przed: {przed}, po: {po}) — połączenia otwarte poza "
        "wątkiem żądania nie są zamykane przez close_old_connections."
    )


def test_brak_globalnej_latki_thread_sensitive():
    """``sync_to_async`` z asgiref ma domyślne ``thread_sensitive=True``.

    Globalna podmiana na ``thread_sensitive=False`` przenosi sync-kod
    middleware'ów (auth, sesje, axes, easyaudit) do wątków puli asyncio,
    których ``close_old_connections`` nie sprząta — patrz docstring modułu.
    """
    import asgiref.sync
    from easyaudit.middleware import easyaudit

    for funkcja in (asgiref.sync.sync_to_async, easyaudit.sync_to_async):
        opakowana = funkcja(lambda: None)
        assert opakowana._thread_sensitive is True, funkcja


def test_aplikacja_produkcyjna_jest_owinieta():
    """``django_bpp.asgi.application`` (gunicorn/uvicorn) ma wrapper na wierzchu.

    Import modułowy CELOWO wcześnie (przy zbieraniu) — późny import
    ``django_bpp.asgi`` zamraża zawężone ALLOWED_HOSTS gałęzi WebSocketów
    (patrz ``mcp_server/tests/conftest.py``).
    """
    assert isinstance(asgi.application, ZamykajPolaczeniaWPuli)
