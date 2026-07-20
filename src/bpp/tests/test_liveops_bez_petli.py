"""Regresja: WebProgress musi działać mimo FAŁSZYWEGO wskaźnika bieżącej pętli.

Sync-API Playwrighta zostawia w wątku workera ustawiony wskaźnik bieżącej
pętli zdarzeń (``asyncio.events._set_running_loop``). Wskaźnik NIE jest
weryfikowany — ``asyncio.get_running_loop()`` zwraca pętlę, która wcale nie
działa. ``asgiref.sync.AsyncToSync.__call__`` sprawdza dokładnie ten wskaźnik
i odmawia pracy: „You cannot use AsyncToSync in the same thread as an async
event loop".

Trafia to KAŻDY późniejszy test w tym samym procesie-workerze — stan jest
globalny dla wątku, nie dziedziczony przez fixture'y. Stąd awarie w testach
bez najmniejszego związku z przeglądarką (``test_analyze_autoskip`` i spółka).

Obejście siedzi w ``src/conftest.py`` (``_zainstaluj_obejscie_liveops_petli``):
zdejmuje wskaźnik na czas samej wysyłki do channel layer. Jest to bezpieczne,
bo ``_push``/``_push_message`` NIE dotykają bazy — więc przełączenie magazynu
w ``asgiref.local.Local`` nie ma jak dotknąć żadnego połączenia.
"""

import asyncio

from liveops.progress import WebProgress


class _FakeLayer:
    def __init__(self):
        self.wyslane = []

    async def group_send(self, kanal, msg):
        self.wyslane.append((kanal, msg))


class _FakeOp:
    def get_channel_name(self):
        return "kanal-testowy"


def _z_falszywym_wskaznikiem(fn):
    poprzedni = asyncio.events._get_running_loop()
    petla = asyncio.new_event_loop()
    try:
        asyncio.events._set_running_loop(petla)
        return fn()
    finally:
        asyncio.events._set_running_loop(poprzedni)
        petla.close()


def test_push_dziala_mimo_falszywego_wskaznika_petli():
    layer = _FakeLayer()
    wp = WebProgress(_FakeOp(), layer)

    _z_falszywym_wskaznikiem(lambda: wp._push("<div>postęp</div>"))

    assert len(layer.wyslane) == 1, layer.wyslane
    kanal, msg = layer.wyslane[0]
    assert kanal == "kanal-testowy"
    assert msg["liveop_html"] == "<div>postęp</div>"


def test_push_message_dziala_mimo_falszywego_wskaznika_petli():
    layer = _FakeLayer()
    wp = WebProgress(_FakeOp(), layer)

    _z_falszywym_wskaznikiem(lambda: wp._push_message({"type": "x", "a": 1}))

    assert layer.wyslane == [("kanal-testowy", {"type": "x", "a": 1})]


def test_wskaznik_wraca_po_wysylce():
    """Obejście nie może zjeść wskaźnika — Playwright potrzebuje go dalej."""
    layer = _FakeLayer()
    wp = WebProgress(_FakeOp(), layer)
    petla = asyncio.new_event_loop()
    poprzedni = asyncio.events._get_running_loop()
    try:
        asyncio.events._set_running_loop(petla)
        wp._push("<div/>")
        assert asyncio.events._get_running_loop() is petla
    finally:
        asyncio.events._set_running_loop(poprzedni)
        petla.close()
