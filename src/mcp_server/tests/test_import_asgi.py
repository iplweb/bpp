"""Zamrożona lista origin-ów WebSocketa — regresja na 403 w live-serwerze.

``AllowedHostsOriginValidator`` z channels to funkcja fabrykująca: czyta
``settings.ALLOWED_HOSTS`` RAZ, przy imporcie ``django_bpp/asgi.py``, i zapieka
wynik. Jeśli ten import wypadnie po tym, jak jakiś test zawęzi
``ALLOWED_HOSTS``, gałąź WebSocketów zostaje zamrożona z jednym hostem na całe
życie procesu workera.

Objaw był oddalony od przyczyny: ``403`` przy handshake'u WebSocketa w
``integration_tests/test_bpp_with_notifications.py``, setki testów później, i
tylko przy pewnym rozkładzie shardów. Na CI wyglądał jak flake Playwrighta.
Pełne rozpoznanie i lekarstwo: docstring ``mcp_server/tests/conftest.py``.
"""

import pytest

from mcp_server.aplikacja import build_application


@pytest.mark.django_db(transaction=True)
def test_zawezenie_hostow_w_tescie_nie_zamraza_galezi_websocketow(settings, uczelnia):
    """Odwzorowuje dokładny przebieg, który to psuł.

    Kolejność jest istotna i jest treścią testu: najpierw zawężenie
    ``ALLOWED_HOSTS`` (tak robi ``_router`` w kilku plikach tego pakietu),
    potem ``build_application()``, które sięga po ``django_asgi_app`` importem
    leniwym. Bez importu wymuszonego w ``conftest.py`` to właśnie tutaj
    zapadałby pierwszy import ``django_bpp.asgi`` w procesie.

    Asercja idzie na ``localhost``, bo to jest origin, którego używa
    ``channels_live_server`` — czyli realny warunek przejścia tamtych testów,
    a nie dowolna własność listy.
    """
    settings.ALLOWED_HOSTS = ["bpp.example.test"]
    build_application()

    # Import CELOWO tutaj, nie na górze modułu: import modułowy wykonuje się
    # przy zbieraniu testów, czyli przed nadpisaniem — i test przechodziłby
    # nawet bez `conftest.py`, czyli byłby zielony z niewłaściwego powodu.
    # Sprawdzone mutacyjnie.
    import django_bpp.asgi

    walidator = django_bpp.asgi.application.application_mapping["websocket"]
    assert "localhost" in walidator.allowed_origins, (
        "gałąź WebSocketów zamrożona z zawężoną listą hostów — live-serwer "
        "będzie odrzucał handshake origin-em localhost z 403"
    )
