"""Regresja: zapisy testu muszą zostać w JEGO transakcji, także po Playwrighcie.

Django trzyma połączenia w ``asgiref.local.Local(thread_critical=True)``, a
``Local._lock_storage()`` wybiera magazyn po ``asyncio.get_running_loop()``:
brak pętli → ``threading.local``, jest pętla → ``cvar``. ZMIANA markera
running-loop w trakcie testu przełącza więc magazyn i ``connections['default']``
zwraca INNE połączenie — świeże, w autocommit, POZA atomic blokiem. Zapisy po
takim przełączeniu commitują się naprawdę, a rollback ``pytest-django`` cofa
pierwsze połączenie i nie ma czego cofać.

Tak wyciekało 79 testów ``import_pracownikow`` na CI: ich conftest miał autouse
fixture, który zerował marker na czas testu i przywracał go w ``finally``.

Reguła, której pilnuje ten test: NIE przestawiać markera wokół testów
używających bazy. Marker ustawiony na stałe (tak go zostawia sync-API
Playwrighta) jest nieszkodliwy — magazyn jest wtedy spójny przez cały cykl.
"""

import asyncio

import pytest
from model_bakery import baker

from bpp.models import Jednostka


@pytest.mark.django_db
def test_zapis_zostaje_w_transakcji_testu():
    from django.db import connection

    assert connection.in_atomic_block, "test DB musi startować w atomic bloku"
    baker.make(Jednostka, nazwa="KANAREK-MARKERA", skrot="KM")
    assert connection.in_atomic_block, "zapis wypadł poza transakcję testu"


@pytest.mark.django_db
def test_przestawienie_markera_wyrzuca_zapis_poza_transakcje():
    """Dokumentuje MECHANIZM — dlatego nie wolno ruszać markera przy żywej DB.

    Nie jest to test „czegoś naszego": pokazuje zachowanie asgiref/Django,
    na które musimy uważać. Gdyby kiedyś przestało zachodzić (zmiana
    w asgiref), ten test padnie i będzie można uprościć regułę wyżej.
    """
    from django.db import connection

    assert connection.in_atomic_block
    poprzedni = asyncio.events._get_running_loop()
    try:
        asyncio.events._set_running_loop(asyncio.new_event_loop())
        from django.db import connection as po_zmianie

        assert not po_zmianie.in_atomic_block, (
            "asgiref przestał przełączać magazyn połączeń po markerze pętli — "
            "regułę o nieruszaniu markera można wtedy przemyśleć na nowo"
        )
    finally:
        asyncio.events._set_running_loop(poprzedni)
