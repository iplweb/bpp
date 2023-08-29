from unittest.mock import MagicMock

import django
import pytest
from django.urls import reverse

from raport_slotow.views.zerowy import RaportSlotowZerowyWyniki

from bpp.models import OpcjaWyswietlaniaField, Uczelnia
from bpp.models.dyscyplina_naukowa import Autor_Dyscyplina
from bpp.models.sloty.core import IPunktacjaCacher
from bpp.models.system import Charakter_Formalny
from bpp.models.wydawca import Wydawca
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte


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


def test_raport_slotow_zerowy_get_querylist_min_pk(fikstura_raportu_slotow):
    jk, jn = fikstura_raportu_slotow
    rszw = RaportSlotowZerowyWyniki(min_pk=200)

    rszw.form = MagicMock()
    rszw.form.cleaned_data = dict()
    rszw.form.cleaned_data["od_roku"] = 2020
    rszw.form.cleaned_data["do_roku"] = 2020
    rszw.form.cleaned_data["min_pk"] = 200
    rszw.form.cleaned_data["rodzaj_raportu"] = "x"

    res = rszw.get_queryset()
    res = res.values_list("autor_id", flat=True)
    assert res.count() == 2


def test_raport_slotow_zerowy_get_querylist(fikstura_raportu_slotow):
    jk, jn = fikstura_raportu_slotow

    rszw = RaportSlotowZerowyWyniki()

    rszw.form = MagicMock()
    rszw.form.cleaned_data = dict()
    rszw.form.cleaned_data["od_roku"] = 2020
    rszw.form.cleaned_data["do_roku"] = 2020
    rszw.form.cleaned_data["min_pk"] = 5
    rszw.form.cleaned_data["rodzaj_raportu"] = "x"

    res = rszw.get_queryset()

    res = res.values_list("autor_id", flat=True)

    assert res.count() == 1
    assert jk.id in res
    assert jn.id not in res


def test_raport_slotow_zerowy_rednering(
    fikstura_raportu_slotow, admin_client: django.test.Client, uczelnia
):
    uczelnia.pokazuj_raport_slotow_zerowy = OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE
    uczelnia.save()
    res = admin_client.get(
        reverse("raport_slotow:raport-slotow-zerowy-wyniki")
        + "?od_roku=2020&do_roku=2020&min_pk=0&rodzaj_raportu=SL&_export=html"
    )
    assert b"Kowalski" in res.content
    assert b"Nowak" not in res.content


def test_raport_slotow_zerowy_formularz_zamowienia(
    admin_client: django.test.Client, uczelnia: Uczelnia
):
    uczelnia.pokazuj_raport_slotow_zerowy = OpcjaWyswietlaniaField.POKAZUJ_ZAWSZE
    uczelnia.save()
    res = admin_client.get(reverse("raport_slotow:raport-slotow-zerowy-parametry"))
    assert res.status_code == 200
