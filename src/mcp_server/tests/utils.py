"""Pomocniki testowe warstwy ASGI.

Repo nie ma ``pytest-asyncio``, a ``async_to_sync`` rzuca, gdy w bieżącym
wątku biegnie już pętla (flaky zależny od kolejności testów — patrz
``django_bpp/tests/test_asgi_notifications.py``). Odpalamy więc każdą korutynę
przez ``asyncio.run`` w dedykowanym wątku ze świeżą pętlą.
"""

import asyncio
import json
from concurrent.futures import ThreadPoolExecutor


def uruchom(coro_factory):
    """Odpal fabrykę korutyn w osobnym wątku i zwróć jej wynik.

    Przyjmujemy FABRYKĘ, nie korutynę: korutyna utworzona w wątku wołającym
    byłaby związana z jego (nieistniejącą) pętlą.
    """
    with ThreadPoolExecutor(max_workers=1) as ex:
        return ex.submit(lambda: asyncio.run(coro_factory())).result()


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
