"""
Tests for ISlot and SlotKalkulator for Wydawnictwo_Zwarte.

For Wydawnictwo_Ciagle tests, see test_sloty_wydawnictwo_ciagle.py
For cache tests, see test_sloty_cache.py
For misc tests, see test_sloty_misc.py
"""

import pytest

from bpp.const import PBN_LATA
from bpp.models import Typ_Odpowiedzialnosci
from bpp.models.sloty.core import ISlot
from bpp.models.sloty.exceptions import CannotAdapt
from bpp.models.sloty.wydawnictwo_zwarte import (
    SlotKalkulator_Wydawnictwo_Zwarte_Prog1,
    SlotKalkulator_Wydawnictwo_Zwarte_Prog2,
    SlotKalkulator_Wydawnictwo_Zwarte_Prog3,
)


def powiel_wpisy_dyscyplin_autorow(wydawnictwo, rok_z, rok_do):
    """Helper function to duplicate discipline entries for authors."""
    for wca in wydawnictwo.autorzy_set.all():
        ad = wca.autor.autor_dyscyplina_set.get(rok=rok_z)
        ad.pk = None
        ad.rok = rok_do
        ad.save()


@pytest.mark.django_db
def test_ISlot_wydawnictwo_zwarte_zakres_lat_nie_ten(zwarte_z_dyscyplinami):
    zwarte_z_dyscyplinami.rok = 2016

    with pytest.raises(CannotAdapt):
        ISlot(zwarte_z_dyscyplinami)

    for rok in PBN_LATA:
        zwarte_z_dyscyplinami.rok = rok
        ISlot(zwarte_z_dyscyplinami)

    rok += 1
    zwarte_z_dyscyplinami.rok = rok
    with pytest.raises(CannotAdapt):
        ISlot(zwarte_z_dyscyplinami)


@pytest.mark.django_db
def test_ISlot_wydawnictwo_zwarte_redakcja_i_autorstwo(zwarte_z_dyscyplinami):
    a1 = zwarte_z_dyscyplinami.autorzy_set.first()
    a1.typ_odpowiedzialnosci = Typ_Odpowiedzialnosci.objects.get(skrot="red.")
    a1.save()

    zwarte_z_dyscyplinami.rok = 2021
    zwarte_z_dyscyplinami.save()

    with pytest.raises(CannotAdapt, match="ma jednocześnie"):
        ISlot(zwarte_z_dyscyplinami)


@pytest.mark.django_db
def test_ISlot_wydawnictwo_zwarte_bez_red_bez_aut(zwarte_z_dyscyplinami):
    zwarte_z_dyscyplinami.autorzy_set.all().delete()
    zwarte_z_dyscyplinami.rok = 2021
    zwarte_z_dyscyplinami.save()

    with pytest.raises(CannotAdapt, match="nie posiada"):
        ISlot(zwarte_z_dyscyplinami)


@pytest.mark.django_db
def test_ISlot_wydawnictwo_Zwarte_nie_te_punkty(zwarte_z_dyscyplinami):
    zwarte_z_dyscyplinami.punkty_kbn = 12345
    zwarte_z_dyscyplinami.rok = 2021
    with pytest.raises(CannotAdapt, match="nie można dopasować do żadnej z grup"):
        ISlot(zwarte_z_dyscyplinami)


@pytest.mark.django_db
def test_ISlot_wydawnictwo_zwarte_tier3(zwarte_z_dyscyplinami):
    zwarte_z_dyscyplinami.rok = 2021
    i = ISlot(zwarte_z_dyscyplinami)
    assert isinstance(i, SlotKalkulator_Wydawnictwo_Zwarte_Prog3)


@pytest.mark.django_db
def test_ISlot_wydawnictwo_zwarte_hst_tier3(zwarte_z_dyscyplinami_hst):
    zwarte_z_dyscyplinami_hst.rok = 2021

    zwarte_z_dyscyplinami_hst.punkty_kbn = 20
    i = ISlot(zwarte_z_dyscyplinami_hst)
    assert isinstance(i, SlotKalkulator_Wydawnictwo_Zwarte_Prog3)

    zwarte_z_dyscyplinami_hst.punkty_kbn = 120
    i = ISlot(zwarte_z_dyscyplinami_hst)
    assert isinstance(i, SlotKalkulator_Wydawnictwo_Zwarte_Prog3)


@pytest.mark.django_db
def test_ISlot_wydawnictwo_zwarte_hst_oraz_nie_hst(
    zwarte_z_dyscyplinami_hst_oraz_nie_hst, rok
):
    zwarte_z_dyscyplinami_hst_oraz_nie_hst.rok = 2021
    zwarte_z_dyscyplinami_hst_oraz_nie_hst.save()

    powiel_wpisy_dyscyplin_autorow(zwarte_z_dyscyplinami_hst_oraz_nie_hst, rok, 2021)

    zwarte_z_dyscyplinami_hst_oraz_nie_hst.punkty_kbn = 20
    i = ISlot(zwarte_z_dyscyplinami_hst_oraz_nie_hst)
    assert isinstance(i, SlotKalkulator_Wydawnictwo_Zwarte_Prog3)

    autorzy = list(zwarte_z_dyscyplinami_hst_oraz_nie_hst.autorzy_set.all())

    assert i.pkd_dla_autora(autorzy[0]) == 15
    assert i.pkd_dla_autora(autorzy[1]) == 10


@pytest.mark.django_db
def test_ISlot_wydawnictwo_zwarte_rozdzial_hst_oraz_nie_hst_prog_1_bez_zwiekszenia(
    zwarte_z_dyscyplinami_hst_oraz_nie_hst, rok, charakter_formalny_rozdzial
):
    wydawca = zwarte_z_dyscyplinami_hst_oraz_nie_hst.wydawca
    wydawca.poziom_wydawcy_set.create(rok=2022, poziom=1)

    zwarte_z_dyscyplinami_hst_oraz_nie_hst.rok = 2022
    zwarte_z_dyscyplinami_hst_oraz_nie_hst.charakter_formalny = (
        charakter_formalny_rozdzial
    )
    zwarte_z_dyscyplinami_hst_oraz_nie_hst.punkty_kbn = 20

    zwarte_z_dyscyplinami_hst_oraz_nie_hst.save()

    powiel_wpisy_dyscyplin_autorow(zwarte_z_dyscyplinami_hst_oraz_nie_hst, rok, 2022)

    i = ISlot(zwarte_z_dyscyplinami_hst_oraz_nie_hst)
    assert isinstance(i, SlotKalkulator_Wydawnictwo_Zwarte_Prog2)

    autorzy = list(zwarte_z_dyscyplinami_hst_oraz_nie_hst.autorzy_set.all())

    # assert i.slot_dla_autora(autorzy[0]) == 0.7
    assert round(i.pkd_dla_autora(autorzy[0]), 0) == 14

    # assert i.slot_dla_autora(autorzy[1]) == 0.7
    assert round(i.pkd_dla_autora(autorzy[1]), 0) == 14


@pytest.mark.django_db
def test_ISlot_wydawnictwo_zwarte_rozdzial_hst_oraz_nie_hst_prog_2_ze_zwiekszaniem(
    zwarte_z_dyscyplinami_hst_oraz_nie_hst, rok, charakter_formalny_rozdzial
):
    zwarte_z_dyscyplinami_hst_oraz_nie_hst.rok = 2022
    zwarte_z_dyscyplinami_hst_oraz_nie_hst.charakter_formalny = (
        charakter_formalny_rozdzial
    )
    zwarte_z_dyscyplinami_hst_oraz_nie_hst.punkty_kbn = 50
    zwarte_z_dyscyplinami_hst_oraz_nie_hst.save()

    wydawca = zwarte_z_dyscyplinami_hst_oraz_nie_hst.wydawca
    wydawca.poziom_wydawcy_set.create(rok=2022, poziom=2)

    powiel_wpisy_dyscyplin_autorow(zwarte_z_dyscyplinami_hst_oraz_nie_hst, rok, 2022)

    i = ISlot(zwarte_z_dyscyplinami_hst_oraz_nie_hst)
    assert isinstance(i, SlotKalkulator_Wydawnictwo_Zwarte_Prog1)

    autorzy = list(zwarte_z_dyscyplinami_hst_oraz_nie_hst.autorzy_set.all())

    assert i.pkd_dla_autora(autorzy[0]) == 75
    assert i.pkd_dla_autora(autorzy[1]) == 50


@pytest.mark.django_db
def test_ISlot_wydawnictwo_zwarte_tier3_rok_2022(zwarte_z_dyscyplinami):
    zwarte_z_dyscyplinami.rok = 2022
    i = ISlot(zwarte_z_dyscyplinami)
    assert isinstance(i, SlotKalkulator_Wydawnictwo_Zwarte_Prog3)


@pytest.mark.django_db
def test_ISlot_wydawnictwo_zwarte_tier2(zwarte_z_dyscyplinami, wydawca):
    rok = 2021
    wydawca.poziom_wydawcy_set.create(rok=rok, poziom=1)
    zwarte_z_dyscyplinami.punkty_kbn = 80
    zwarte_z_dyscyplinami.rok = rok
    i = ISlot(zwarte_z_dyscyplinami)
    assert isinstance(i, SlotKalkulator_Wydawnictwo_Zwarte_Prog2)


@pytest.mark.django_db
def test_ISlot_wydawnictwo_zwarte_hst_tier2(zwarte_z_dyscyplinami_hst, wydawca):
    rok = 2021
    wydawca.poziom_wydawcy_set.create(rok=rok, poziom=1)
    zwarte_z_dyscyplinami_hst.punkty_kbn = 120
    zwarte_z_dyscyplinami_hst.rok = rok
    i = ISlot(zwarte_z_dyscyplinami_hst)
    assert isinstance(i, SlotKalkulator_Wydawnictwo_Zwarte_Prog2)


@pytest.mark.django_db
def test_ISlot_wydawnictwo_zwarte_tier1(zwarte_z_dyscyplinami, wydawca):
    rok = 2021
    wydawca.poziom_wydawcy_set.create(rok=rok, poziom=2)
    zwarte_z_dyscyplinami.punkty_kbn = 200
    zwarte_z_dyscyplinami.rok = rok
    i = ISlot(zwarte_z_dyscyplinami)
    assert isinstance(i, SlotKalkulator_Wydawnictwo_Zwarte_Prog1)


@pytest.mark.django_db
def test_ISlot_wydawnictwo_zwarte_hst_tier1(zwarte_z_dyscyplinami_hst, wydawca):
    rok = 2021
    wydawca.poziom_wydawcy_set.create(rok=rok, poziom=2)
    zwarte_z_dyscyplinami_hst.punkty_kbn = 300
    zwarte_z_dyscyplinami_hst.rok = rok
    i = ISlot(zwarte_z_dyscyplinami_hst)
    assert isinstance(i, SlotKalkulator_Wydawnictwo_Zwarte_Prog1)


@pytest.mark.django_db
def test_ISlot_wydawnictwo_zwarte_hst_tier1_redakcja(
    zwarte_z_dyscyplinami_hst, wydawca, typ_odpowiedzialnosci_redaktor
):
    rok = 2021
    wydawca.poziom_wydawcy_set.create(rok=rok, poziom=2)
    for autor in zwarte_z_dyscyplinami_hst.autorzy_set.all():
        autor.typ_odpowiedzialnosci = typ_odpowiedzialnosci_redaktor
        autor.save()
    zwarte_z_dyscyplinami_hst.punkty_kbn = 150
    zwarte_z_dyscyplinami_hst.rok = rok
    i = ISlot(zwarte_z_dyscyplinami_hst)
    assert isinstance(i, SlotKalkulator_Wydawnictwo_Zwarte_Prog1)


@pytest.mark.django_db
def test_ISlot_wydawnictwo_zwarte_hst_tier2_redakcja(
    zwarte_z_dyscyplinami_hst, wydawca, typ_odpowiedzialnosci_redaktor
):
    rok = 2021
    wydawca.poziom_wydawcy_set.create(rok=rok, poziom=1)
    for autor in zwarte_z_dyscyplinami_hst.autorzy_set.all():
        autor.typ_odpowiedzialnosci = typ_odpowiedzialnosci_redaktor
        autor.save()
    zwarte_z_dyscyplinami_hst.punkty_kbn = 40
    zwarte_z_dyscyplinami_hst.rok = rok
    i = ISlot(zwarte_z_dyscyplinami_hst)
    assert isinstance(i, SlotKalkulator_Wydawnictwo_Zwarte_Prog2)


@pytest.mark.django_db
def test_ISlot_wydawnictwo_zwarte_hst_tier3_redakcja(
    zwarte_z_dyscyplinami_hst, wydawca, typ_odpowiedzialnosci_redaktor
):
    rok = 2021
    for autor in zwarte_z_dyscyplinami_hst.autorzy_set.all():
        autor.typ_odpowiedzialnosci = typ_odpowiedzialnosci_redaktor
        autor.save()

    zwarte_z_dyscyplinami_hst.rok = rok

    zwarte_z_dyscyplinami_hst.punkty_kbn = 10
    i = ISlot(zwarte_z_dyscyplinami_hst)
    assert isinstance(i, SlotKalkulator_Wydawnictwo_Zwarte_Prog3)

    zwarte_z_dyscyplinami_hst.punkty_kbn = 20
    i = ISlot(zwarte_z_dyscyplinami_hst)
    assert isinstance(i, SlotKalkulator_Wydawnictwo_Zwarte_Prog3)


@pytest.mark.django_db
def test_ISlot_wydawnictwo_zwarte_hst_tier1_autorstwo(
    zwarte_z_dyscyplinami_hst, wydawca, charakter_formalny_rozdzial
):
    rok = 2021
    wydawca.poziom_wydawcy_set.create(rok=rok, poziom=2)
    zwarte_z_dyscyplinami_hst.charakter_formalny = charakter_formalny_rozdzial
    zwarte_z_dyscyplinami_hst.punkty_kbn = 75
    zwarte_z_dyscyplinami_hst.rok = rok
    i = ISlot(zwarte_z_dyscyplinami_hst)
    assert isinstance(i, SlotKalkulator_Wydawnictwo_Zwarte_Prog1)


@pytest.mark.django_db
def test_ISlot_wydawnictwo_zwarte_hst_tier2_autorstwo(
    zwarte_z_dyscyplinami_hst, wydawca, charakter_formalny_rozdzial
):
    rok = 2021
    wydawca.poziom_wydawcy_set.create(rok=rok, poziom=1)
    zwarte_z_dyscyplinami_hst.charakter_formalny = charakter_formalny_rozdzial
    zwarte_z_dyscyplinami_hst.punkty_kbn = 20
    zwarte_z_dyscyplinami_hst.rok = rok
    i = ISlot(zwarte_z_dyscyplinami_hst)
    assert isinstance(i, SlotKalkulator_Wydawnictwo_Zwarte_Prog2)


@pytest.mark.django_db
def test_ISlot_wydawnictwo_zwarte_hst_tier3_autorstwo(
    zwarte_z_dyscyplinami_hst, wydawca, charakter_formalny_rozdzial
):
    rok = 2021
    zwarte_z_dyscyplinami_hst.charakter_formalny = charakter_formalny_rozdzial
    zwarte_z_dyscyplinami_hst.rok = rok

    zwarte_z_dyscyplinami_hst.punkty_kbn = 5
    i = ISlot(zwarte_z_dyscyplinami_hst)
    assert isinstance(i, SlotKalkulator_Wydawnictwo_Zwarte_Prog3)

    zwarte_z_dyscyplinami_hst.punkty_kbn = 20
    i = ISlot(zwarte_z_dyscyplinami_hst)
    assert isinstance(i, SlotKalkulator_Wydawnictwo_Zwarte_Prog3)


@pytest.mark.django_db
def test_ISlot_wydawnictwo_zwarte_tier1_brak_afiliacji(
    zwarte_z_dyscyplinami, wydawca, rok, dyscyplina1, dyscyplina2
):
    _rok = 2021
    wydawca.poziom_wydawcy_set.create(rok=_rok, poziom=2)
    zwarte_z_dyscyplinami.punkty_kbn = 200
    zwarte_z_dyscyplinami.rok = _rok
    zwarte_z_dyscyplinami.save()

    powiel_wpisy_dyscyplin_autorow(zwarte_z_dyscyplinami, rok, 2021)

    i = ISlot(zwarte_z_dyscyplinami)
    assert i.autorzy_z_dyscypliny(dyscyplina1)

    zwarte_z_dyscyplinami.autorzy_set.update(afiliuje=False)
    assert not i.autorzy_z_dyscypliny(dyscyplina1)
