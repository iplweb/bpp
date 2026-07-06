import pytest
from model_bakery import baker


@pytest.mark.django_db
def test_create_report_zawezony_po_uczelni(
    zwarte_dwie_uczelnie, jednostka, druga_uczelnia, rok
):
    from raport_slotow.models.uczelnia import RaportSlotowUczelnia

    zwarte_dwie_uczelnie.przelicz_punkty_dyscyplin()

    raport = baker.make(
        RaportSlotowUczelnia,
        od_roku=rok,
        do_roku=rok,
        uczelnia=jednostka.uczelnia,
        akcja=RaportSlotowUczelnia.Akcje.WSZYSTKO,
    )
    raport.create_report()

    jednostki_w_raporcie = set(
        raport.raportslotowuczelniawiersz_set.values_list(
            "jednostka__uczelnia_id", flat=True
        )
    )
    assert jednostki_w_raporcie <= {jednostka.uczelnia_id}
    assert druga_uczelnia.pk not in jednostki_w_raporcie
