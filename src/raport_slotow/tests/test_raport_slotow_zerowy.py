import django
import pytest
from django.urls import reverse

from bpp.models.dyscyplina_naukowa import Autor_Dyscyplina
from bpp.models.sloty.core import IPunktacjaCacher
from bpp.models.system import Charakter_Formalny
from bpp.models.wydawca import Wydawca
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from raport_slotow.views import RaportSlotowZerowy


@pytest.fixture
def fikstura_raportu_slotow(
    autor_jan_kowalski,
    autor_jan_nowak,
    jednostka,
    dyscyplina1,
    wydawnictwo_zwarte: Wydawnictwo_Zwarte,
    charaktery_formalne,
    typy_odpowiedzialnosci,
):
    # Nowak ma przypisanie na dany rok i ma prace
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak, rok=2020, dyscyplina_naukowa=dyscyplina1
    )

    wydawca = Wydawca.objects.create(nazwa="Wydawca")
    wydawca.poziom_wydawcy_set.create(rok=2020, poziom=1)

    wydawnictwo_zwarte.wydawca = wydawca
    wydawnictwo_zwarte.charakter_formalny = Charakter_Formalny.objects.get(skrot="KSP")
    wydawnictwo_zwarte.rok = 2020
    wydawnictwo_zwarte.punkty_kbn = 100
    wydawnictwo_zwarte.dodaj_autora(
        autor=autor_jan_nowak,
        jednostka=jednostka,
        typ_odpowiedzialnosci_skrot="aut.",
        dyscyplina_naukowa=dyscyplina1,
    )

    wydawnictwo_zwarte.save()

    IPunktacjaCacher(wydawnictwo_zwarte).rebuildEntries()

    # Kowalski ma przypisanie i nie ma żadnych prac
    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, rok=2020, dyscyplina_naukowa=dyscyplina1
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
