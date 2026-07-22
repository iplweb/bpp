"""Test integracyjny ścieżki ASGI liveops: WebProgress → channel layer → odbiór.

DLACZEGO ISTNIEJE. Testy jednostkowe raportują postęp przez ``MockProgress``
(patrz ``_zainstaluj_testowy_progress_liveops`` w ``src/conftest.py``), bo
produkcyjny ``WebProgress`` pcha każdy krok przez
``async_to_sync(channel_layer.group_send)``, a to wywraca się o żywą, zaparkowaną
w greenlecie pętlę zdarzeń, którą sync-API Playwrighta trzyma w wątku workera.
Skutkiem tej podmiany prawdziwa ścieżka ASGI przestała być w testach
przebiegana — i właśnie dlatego musi ją pokryć TEN test.

CO POKRYWA: że ``WebProgress`` faktycznie dostarcza komunikat do grupy przez
REALNY channel layer (Redis z testcontainera), w formacie, którego oczekuje
konsument (koperta ``{"type": "chat_message", "liveop_html": ...}``).

CZEGO NIE POKRYWA: konsumenta WebSocket ani renderowania paska postępu
w przeglądarce. To osobna warstwa; tutaj sprawdzamy transport.

DLACZEGO W WĄTKU. ``async_to_sync`` odmawia pracy, gdy w bieżącym wątku jest
zarejestrowana działająca pętla zdarzeń — a po dowolnym teście Playwright na
tym samym workerze xdist właśnie tak jest. Świeży wątek żadnej pętli nie ma,
więc test jest odporny na kolejność shardowania. Odpowiada to zresztą
produkcji, gdzie liveops chodzi pod celery/threading, a nie w wątku
z zaparkowaną pętlą Playwrighta.
"""

from concurrent.futures import ThreadPoolExecutor

import pytest
from channels.layers import get_channel_layer
from liveops.progress import WebProgress

KANAL = "liveop-test-kanal"


class _Operacja:
    """Minimalny dubler ``LiveOperation`` — test dotyczy TRANSPORTU, nie ORM-u."""

    def get_channel_name(self):
        return KANAL


def _wyslij_i_odbierz(html):
    """Cały obieg w świeżym wątku — patrz „DLACZEGO W WĄTKU" w docstringu."""
    from asgiref.sync import async_to_sync

    layer = get_channel_layer()
    nazwa_odbiorcy = async_to_sync(layer.new_channel)()
    async_to_sync(layer.group_add)(KANAL, nazwa_odbiorcy)
    try:
        WebProgress(_Operacja(), layer)._push(html)
        return async_to_sync(layer.receive)(nazwa_odbiorcy)
    finally:
        async_to_sync(layer.group_discard)(KANAL, nazwa_odbiorcy)


@pytest.mark.timeout(30)
def test_webprogress_dostarcza_html_do_grupy():
    html = "<div id='postep'>42%</div>"
    with ThreadPoolExecutor(max_workers=1) as ex:
        wiadomosc = ex.submit(_wyslij_i_odbierz, html).result(timeout=20)

    assert wiadomosc["type"] == "chat_message", wiadomosc
    assert wiadomosc["liveop_html"] == html, wiadomosc
