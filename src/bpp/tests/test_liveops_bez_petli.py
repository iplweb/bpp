"""Regresja: w testach liveops NIE może chodzić przez channel layer.

``liveops.runner._make_progress`` domyślnie wybiera ``WebProgress``, który
pcha każdy krok postępu przez ``async_to_sync(channel_layer.group_send)``.
W testach ta ścieżka jest niepotrzebna (nikt nie słucha po WebSocket)
i aktywnie szkodliwa: sync-API Playwrighta trzyma w wątku workera żywą,
zaparkowaną w greenlecie pętlę zdarzeń, a ``AsyncToSync`` odmawia wtedy
pracy („You cannot use AsyncToSync in the same thread as an async event
loop"). Stan jest globalny dla wątku, więc obrywał każdy późniejszy test
w procesie — także bez związku z przeglądarką.

Podmiana na ``MockProgress`` siedzi w ``src/conftest.py``.
"""

import asyncio

import pytest
from model_bakery import baker

from bpp.models import Jednostka


def test_liveops_uzywa_testowego_progressu():
    from liveops.runner import _make_progress
    from liveops.testing import MockProgress

    class _FakeOp:
        def get_channel_name(self):
            return "kanal"

    assert isinstance(_make_progress(_FakeOp()), MockProgress)


def test_progress_dziala_gdy_petla_zaparkowana_w_watku():
    """Przy ustawionym wskaźniku bieżącej pętli budowa progressu i raportowanie
    muszą przejść bez wyjątku.

    UWAGA co do siły dowodu: bez podmiany w ``src/conftest.py`` ten test też
    pada, ale na ``Database access not allowed`` (``WebProgress`` sięga do
    bazy), a nie na ``AsyncToSync``. Sprawdza więc WŁASNOŚĆ, na której nam
    zależy (progress działa mimo zaparkowanej pętli), a nie konkretny
    mechanizm awarii. Czystym kontrfaktykiem jest test wyżej."""
    from liveops.runner import _make_progress

    class _FakeOp:
        pk = None
        finished_on = None
        finished_successfully = None
        result_context = None

        def get_channel_name(self):
            return "kanal"

    poprzednia = asyncio.events._get_running_loop()
    petla = asyncio.new_event_loop()
    try:
        asyncio.events._set_running_loop(petla)
        p = _make_progress(_FakeOp())
        p.log("krok")
        p.percent(50)
        assert p.logs == ["krok"]
        assert 50 in p.percents
    finally:
        asyncio.events._set_running_loop(poprzednia)
        petla.close()


@pytest.mark.django_db
def test_zapis_zostaje_w_transakcji_testu():
    """Kanarek: gdyby coś znów przestawiło wskaźnik pętli przy żywej bazie,
    zapis wypadłby poza atomic block i scommitował się na trwałe."""
    from django.db import connection

    assert connection.in_atomic_block
    baker.make(Jednostka, nazwa="KANAREK-LIVEOPS", skrot="KL")
    assert connection.in_atomic_block
