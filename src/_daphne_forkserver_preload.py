"""Preload Django w procesie forkservera ``multiprocessing`` (testy Daphne).

Od Pythona 3.14 domyślną metodą startu procesów na Linuksie jest
``forkserver``: ``DaphneProcess`` (``channels_live_server._spawn_daphne``)
forkuje się z czystego interpretera forkservera i KAŻDY Daphne importował
całe Django + BPP od zera (~1,5 s na proces). W przebiegu Playwright to
~30 procesów (fikstury ``*_per_test``, Freshworks, captcha) — w profilu
py-spy import modułów był połową CPU wszystkich procesów Daphne.

``channels_live_server`` rejestruje ten moduł przez
``multiprocessing.set_forkserver_preload``, więc forkserver workera xdist
wykonuje ``django.setup()`` RAZ, a każde dziecko dziedziczy gotowe moduły
(copy-on-write) — jak przy dawnym ``fork`` sprzed 3.14.

Bezpieczne, bo:

- ``DaphneProcess.run`` w dziecku i tak woła ``_reinstall_reactor()`` —
  nowa pętla asyncio i nowy reaktor Twisted, zamiast odziedziczonego
  (``daphne.server`` instaluje reaktor już przy ``django.setup()``),
- ``django.setup()`` ani import URL-i nie otwierają połączenia z bazą;
  dziecko ustawia nazwę testowej bazy (``set_database_connection``) przed
  pierwszym zapytaniem, a ustawienia (``setup=`` z testów Freshworks /
  captcha) mutuje po forku — dokładnie jak wcześniej.

Błąd preloadu nie może zepsuć testów: forkserver połyka tylko
``ImportError``, więc wszystko inne łapiemy tutaj, wypisujemy traceback i
dzieci wracają do dotychczasowego, wolniejszego importu po forku.
"""

import traceback

try:
    import django

    django.setup()

    # Ciężkie importy widoków/adminu i modułów, które ładuje
    # ``django_bpp.asgi``. Samego ``django_bpp.asgi`` celowo NIE importujemy:
    # przy imporcie buduje aplikację MCP z ``settings`` — niech robi to
    # dziecko, jak dotąd.
    import channels.auth  # noqa: F401
    import liveops.routing  # noqa: F401

    import django_bpp.urls  # noqa: F401
    import mcp_server.aplikacja  # noqa: F401
    import mcp_server.routing  # noqa: F401
except Exception:
    # Celowo bez raise: wyjątek zabiłby forkserver, a bez preloadu dzieci
    # po prostu importują Django same (stare zachowanie).
    traceback.print_exc()
