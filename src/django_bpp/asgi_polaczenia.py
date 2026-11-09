"""Sprzątanie połączeń z bazą w wątkach domyślnego executora pętli ASGI.

Django trzyma połączenia per wątek, a ``close_old_connections`` (sygnały
``request_started``/``request_finished``) sprząta wyłącznie wątek żądania.
Część sync-kodu biegnie jednak przez ``sync_to_async(..., thread_sensitive=False)``,
czyli ``loop.run_in_executor(None, ...)`` — w wątkach DOMYŚLNEGO executora pętli,
które żyją tak długo jak worker. Robi tak samo Django (``convert_exception_to_response``
renderuje 404/403/500 — z zapytaniami do bazy w ``handler404`` — oraz
``log_response``), a także biblioteki trzecie. Połączenie otwarte w takim wątku
nigdy nie było zamykane: na produkcji wisiały ich dziesiątki jako ``idle``
(ostatnie zapytanie ``set_config('TimeZone', …)``) i zapychały pulę pgbouncera.

Rozwiązanie: domyślny executor pętli zamienia się na taki, który po KAŻDYM
zadaniu zamyka połączenia Django w swoim wątku. Zadanie ``thread_sensitive=False``
z definicji nie ma gwarancji, że następne trafi do tego samego wątku, więc nic
nie może polegać na tym, że połączenie z niego przetrwa.
"""

import asyncio
import weakref
from concurrent.futures import ThreadPoolExecutor

from django.db import connections


def _uruchom_i_zamknij_polaczenia(funkcja, /, *args, **kwargs):
    try:
        return funkcja(*args, **kwargs)
    finally:
        # Tylko połączenia TEGO wątku (ConnectionHandler jest thread-local).
        connections.close_all()


class ExecutorZamykajacyPolaczenia(ThreadPoolExecutor):
    """``ThreadPoolExecutor`` zamykający połączenia Django po każdym zadaniu."""

    def submit(self, fn, /, *args, **kwargs):
        return super().submit(_uruchom_i_zamknij_polaczenia, fn, *args, **kwargs)


class ZamykajPolaczeniaWPuli:
    """Wrapper ASGI: w każdej pętli, w której biegnie aplikacja, podmienia
    domyślny executor na :class:`ExecutorZamykajacyPolaczenia`.

    Instalacja leniwie przy pierwszym wywołaniu (pierwszym jest zwykle
    ``lifespan``), bo pętlę tworzy serwer (uvicorn/daphne), nie my.
    """

    def __init__(self, aplikacja):
        self.aplikacja = aplikacja
        self._petle = weakref.WeakSet()

    async def __call__(self, scope, receive, send):
        petla = asyncio.get_running_loop()
        if petla not in self._petle:
            petla.set_default_executor(
                ExecutorZamykajacyPolaczenia(thread_name_prefix="bpp-asgi-pula")
            )
            self._petle.add(petla)
        return await self.aplikacja(scope, receive, send)
