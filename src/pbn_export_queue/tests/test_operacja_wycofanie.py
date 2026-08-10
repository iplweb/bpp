"""Faza 05 soft-delete: wycofanie oświadczeń dyscyplin z PBN.

Soft-delete publikacji, która poszła do PBN, musi wycofać jej oświadczenia
z profilu instytucji. Realizuje to nowa operacja ``WYCOFANIE`` w kolejce
eksportu, obok dotychczasowej ``WYSYLKA``.
"""

import pytest
from model_bakery import baker

from pbn_export_queue.models import PBN_Export_Queue


@pytest.mark.django_db
def test_operacja_default_wysylka(wydawnictwo_ciagle, admin_user):
    """Wpisy sprzed fazy 05 (i wszystkie tworzone bez jawnej operacji)
    muszą nadal znaczyć „wyślij" — inaczej migracja zamieniłaby zaległą
    kolejkę wysyłek w kolejkę wycofań."""
    wpis = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=admin_user,
    )
    wpis.refresh_from_db()
    assert wpis.operacja == PBN_Export_Queue.Operacja.WYSYLKA
    assert PBN_Export_Queue.Operacja.WYSYLKA == "wysylka"
    assert PBN_Export_Queue.Operacja.WYCOFANIE == "wycofanie"
