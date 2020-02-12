import django
import pytest
from django.urls import reverse

from bpp.models.dyscyplina_naukowa import Autor_Dyscyplina
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from raport_slotow.views import RaportSlotowZerowy


@pytest.fixture
def fikstura_raportu_slotow(
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
    dyscyplina1,
    wydawnictwo_zwarte: Wydawnictwo_Zwarte,
):
    # Nowak ma przypisanie na dany rok i ma prace
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak, rok=2000, dyscyplina_naukowa=dyscyplina1
    )
    wydawnictwo_zwarte.dodaj_autora(
        autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1
    )
    wydawnictwo_zwarte.rok = 2000
    wydawnictwo_zwarte.save()

    # Kowalski ma przypisanie i nie ma żadnych prac
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, rok=2000, dyscyplina_naukowa=dyscyplina1
    )

    return (autor_jan_kowalski, autor_jan_nowak)


def test_raport_slotow_zerowy_get_querylist(fikstura_raportu_slotow):
    jk, jn = fikstura_raportu_slotow

    res = RaportSlotowZerowy().get_queryset()

    res = res.values_list("autor_id", flat=True)

    assert res.count() == 1
    assert jk.id in res
    assert jn.id not in res


def test_raport_slotow_zerowy_rednering(
    fikstura_raportu_slotow, admin_client: django.test.Client
):
    res = admin_client.get(reverse("raport_slotow:raport-slotow-zerowy"))
    assert b"Kowalski" in res.content
    assert b"Nowak" not in res.content
