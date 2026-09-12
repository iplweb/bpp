"""Test chroniący faktyczny montaż MCP w ``django_bpp.asgi.application``.

Żaden inny test nie dotyka ``django_bpp.asgi`` — ``test_e2e.py`` i reszta
testów ``mcp_server`` budują ``RouterHttp``/``LifespanMcp`` własnoręcznie
przez ``build_application()``, więc przechodzą identycznie, nawet gdy ktoś
(np. przy konflikcie merge'a) przywróci w ``asgi.py`` stary
``"http": django_asgi_app`` i usunie klucz ``"lifespan"``. Cały pakiet
świeciłby wtedy zielono, a produkcja nigdy nie odpowiadałaby na ``/mcp``
(gunicorn loguje tylko „lifespan appears unsupported" i jedzie dalej).

Musi być SUBPROCESEM: ``build_application()`` w ``asgi.py`` wykonuje się
raz, przy pierwszym imporcie modułu, i ta jedna instancja żyje tyle, co
proces — ``session_manager.run()`` wchodzi się raz na instancję (patrz
``mcp_server/start.py``). W procesie pytest wszystkie testy dzielą już
zaimportowany ``django_bpp.asgi`` z poprzednich testów (import jest
cache'owany w ``sys.modules``), więc nie da się tu uzyskać świeżej,
nieużywanej instancji — subproces daje czysty import i pełną izolację.
"""

import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]

# Skrypt sprawdza DWIE rzeczy niezależnie:
# 1. strukturę application_mapping (to jest to, co pada, gdy ktoś przywróci
#    stary blok "http": django_asgi_app i usunie klucz "lifespan"),
# 2. że lifespan realnie się otwiera i zamyka PRZEZ ProtocolTypeRouter
#    (nie przez LifespanMcp zbudowany osobno w teście) — startup.complete
#    musi się pojawić w wysłanych komunikatach, inaczej menedżer sesji MCP
#    nigdy nie wstaje (spec §2.4, §5.1).
SKRYPT = """
import asyncio

import django_bpp.asgi as m
from mcp_server.routing import LifespanMcp, RouterHttp

mapowanie = m.application.application_mapping
assert isinstance(mapowanie["http"], RouterHttp), (
    f"'http' to {type(mapowanie['http'])!r}, nie RouterHttp — MCP nie jest "
    "zamontowane obok Django."
)
assert isinstance(mapowanie["lifespan"], LifespanMcp), (
    f"'lifespan' to {type(mapowanie.get('lifespan'))!r}, nie LifespanMcp — "
    "menedżer sesji MCP nigdy nie wstanie pod uvicornem/gunicornem."
)


async def przejdz_cykl_lifespan():
    wyslane = []

    async def send(msg):
        wyslane.append(msg)

    kolejka = [{"type": "lifespan.startup"}, {"type": "lifespan.shutdown"}]

    async def receive():
        return kolejka.pop(0)

    # Przez application (ProtocolTypeRouter), nie przez LifespanMcp z boku —
    # to sprawdza też, że router faktycznie dysponuje scope["type"]=="lifespan".
    await m.application({"type": "lifespan"}, receive, send)
    return wyslane


wyslane = asyncio.run(przejdz_cykl_lifespan())
typy = [m["type"] for m in wyslane]
assert typy == ["lifespan.startup.complete", "lifespan.shutdown.complete"], typy
print("OK")
"""


def test_application_mapping_montuje_mcp_i_lifespan_wstaje():
    """``django_bpp.asgi.application`` musi realnie obsługiwać /mcp i lifespan.

    Odpalone jako osobny proces (patrz docstring modułu) z tym samym
    ``os.environ`` co proces pytest — w tym ``DJANGO_SETTINGS_MODULE``,
    które ustawia pytest-django (``--ds=django_bpp.settings.test``), oraz
    zmienne testcontainers wstrzyknięte przez fixture. Test nie dotyka ORM
    (nie ma ``@pytest.mark.django_db``) — sprawdza strukturę routera
    i cykl lifespanu, obu bez zapytań do bazy.
    """
    wynik = subprocess.run(
        [sys.executable, "-c", SKRYPT],
        cwd=REPO_ROOT,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert wynik.returncode == 0, (
        "MCP nie jest poprawnie zamontowane w django_bpp.asgi.application.\n"
        f"STDOUT:\n{wynik.stdout}\n\nSTDERR:\n{wynik.stderr}"
    )
    assert "OK" in wynik.stdout
