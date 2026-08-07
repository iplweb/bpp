"""Soft-delete PUBLIKACJI (faza 02).

Testy wąskiej, kontrolowanej kaskady `publikacja -> *_Autor` pod wspólnym
`transaction_id`, bez refleksyjnej kaskady pakietu `django-soft-delete`
(która ruszyłaby `*_Streszczenie` i inne nie-soft dzieci).
"""

import pytest
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor


@pytest.mark.django_db
def test_soft_delete_publikacji_kaskaduje_na_autor_wspolny_txid():
    wc = baker.make(Wydawnictwo_Ciagle)
    # `kolejnosc` JAWNIE różna. Bez tego `baker` nadaje obu wierszom 0, co
    # łamie ograniczenie wykluczające `wc_autor_excl_rekord_kolejnosc`
    # (faza 01). Ograniczenie jest DEFERRABLE i warunkowane
    # `deleted_at IS NULL`, więc soft-delete wyprowadzał oba wiersze poza
    # jego zakres, zanim zdążyło zadziałać przy COMMIT — test przechodził
    # wtedy CZĘŚCIOWO z powodu efektu ubocznego, a nie samej kaskady.
    a1 = baker.make(Wydawnictwo_Ciagle_Autor, rekord=wc, kolejnosc=0)
    a2 = baker.make(Wydawnictwo_Ciagle_Autor, rekord=wc, kolejnosc=1)

    wc.delete()

    wc.refresh_from_db()
    assert wc.deleted_at is not None
    assert wc.transaction_id is not None

    for a in (a1, a2):
        row = Wydawnictwo_Ciagle_Autor.global_objects.get(pk=a.pk)
        assert row.deleted_at is not None, "autorstwo nie zostało soft-skasowane"
        assert row.transaction_id == wc.transaction_id, "różny transaction_id"
