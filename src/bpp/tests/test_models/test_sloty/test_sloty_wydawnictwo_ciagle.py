"""
Tests for ISlot and SlotKalkulator for Wydawnictwo_Ciagle.

For Wydawnictwo_Zwarte tests, see test_sloty_wydawnictwo_zwarte.py
For cache tests, see test_sloty_cache.py
For misc tests, see test_sloty_misc.py
"""

from decimal import Decimal

import pytest

from bpp.const import TO_AUTOR, TO_REDAKTOR
from bpp.models import Autor_Dyscyplina
from bpp.models.sloty.core import ISlot
from bpp.models.sloty.exceptions import CannotAdapt
from bpp.models.sloty.wydawnictwo_ciagle import (
    SlotKalkulator_Wydawnictwo_Ciagle_Prog2,
    SlotKalkulator_Wydawnictwo_Ciagle_Prog3,
)


def powiel_wpisy_dyscyplin_autorow(wydawnictwo, rok_z, rok_do):
    """Helper function to duplicate discipline entries for authors."""
    for wca in wydawnictwo.autorzy_set.all():
        ad = wca.autor.autor_dyscyplina_set.get(rok=rok_z)
        ad.pk = None
        ad.rok = rok_do
        ad.save()


@pytest.mark.parametrize(
    "rekord,ustaw_rok,punkty_kbn",
    [
        # (pytest.lazy_fixture("wydawnictwo_zwarte"), 2017, 20),
        (pytest.lazy_fixture("wydawnictwo_ciagle"), 2017, 30)
    ],
)
@pytest.mark.django_db
def test_slot_wszyscy_slot_wszystkie_dyscypliny(
    rekord,
    ustaw_rok,
    punkty_kbn,
    autor_jan_kowalski,
    autor_jan_nowak,
    dyscyplina1,
    dyscyplina2,
    jednostka,
    typy_odpowiedzialnosci,
):
    rekord.rok = ustaw_rok
    rekord.punkty_kbn = punkty_kbn
    rekord.save()

    Autor_Dyscyplina.objects.create(
        autor=autor_jan_nowak,
        dyscyplina_naukowa=dyscyplina1,
        rok=ustaw_rok,
    )

    rekord.dodaj_autora(autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1)

    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski,
        dyscyplina_naukowa=dyscyplina2,
        rok=ustaw_rok,
    )
    rekord.dodaj_autora(autor_jan_kowalski, jednostka, dyscyplina_naukowa=dyscyplina2)

    slot = ISlot(rekord)

    assert len(slot.dyscypliny) == 2
    assert slot.wszyscy() == 2


@pytest.mark.django_db
def test_autorzy_z_dyscypliny(
    ciagle_z_dyscyplinami,
    autor_jan_nowak,
    autor_jan_kowalski,
    dyscyplina1,
    dyscyplina2,
    dyscyplina3,
    rok,
):
    ciagle_z_dyscyplinami.punkty_kbn = 30
    ciagle_z_dyscyplinami.rok = 2017
    ciagle_z_dyscyplinami.save()

    powiel_wpisy_dyscyplin_autorow(ciagle_z_dyscyplinami, rok, 2017)

    slot = ISlot(ciagle_z_dyscyplinami)

    assert len(slot.autorzy_z_dyscypliny(dyscyplina1)) == 1
    assert len(slot.autorzy_z_dyscypliny(dyscyplina2)) == 1
    assert len(slot.autorzy_z_dyscypliny(dyscyplina3)) == 0

    assert len(slot.autorzy_z_dyscypliny(dyscyplina1, TO_AUTOR)) == 1
    assert len(slot.autorzy_z_dyscypliny(dyscyplina2, TO_AUTOR)) == 1
    assert len(slot.autorzy_z_dyscypliny(dyscyplina3, TO_AUTOR)) == 0

    assert len(slot.autorzy_z_dyscypliny(dyscyplina1, TO_REDAKTOR)) == 0
    assert len(slot.autorzy_z_dyscypliny(dyscyplina2, TO_REDAKTOR)) == 0
    assert len(slot.autorzy_z_dyscypliny(dyscyplina3, TO_REDAKTOR)) == 0

    # Sprawdź, czy 'autorzy_z_dyscypliny' zwraca tylko afiliowanych (#927)
    # Pierwszy autor to Jan Nowak z dyscyplina "memetyka stosowana" czyli dyscyplina1
    # Wcześniej przypisz tego autora do tej dyscypliny na ten rok

    # Autor_Dyscyplina.objects.create(
    #     autor=autor_jan_nowak, rok=2017, dyscyplina_naukowa=dyscyplina1
    # )

    wca1 = ciagle_z_dyscyplinami.autorzy_set.first()

    wca1.afiliuje = True
    wca1.save()
    assert len(slot.autorzy_z_dyscypliny(dyscyplina1)) == 1

    wca1.afiliuje = False
    wca1.save()
    assert len(slot.autorzy_z_dyscypliny(dyscyplina1)) == 0


@pytest.mark.django_db
@pytest.mark.parametrize(
    "ustaw_rok,punkty,ma_byc_1,ma_byc_2",
    [
        (2017, 30, "30.0000", "1.0000"),
        (2017, 20, "14.1421", "0.7071"),
        (2017, 25, "17.6777", "0.7071"),
        (2017, 15, "7.5000", "0.5000"),
        (2017, 5, "2.5000", "0.5000"),
        (2019, 200, "200.0000", "1.0000"),
        (2019, 140, "140.0000", "1.0000"),
        (2019, 100, "100.0000", "1.0000"),
        (2019, 70, "49.4975", "0.7071"),
        (2019, 40, "28.2843", "0.7071"),
        (2019, 20, "10.0000", "0.5000"),
        (2019, 5, "2.5000", "0.5000"),
    ],
)
def test_slot_artykuly(
    ciagle_z_dyscyplinami,
    autor_jan_nowak,
    autor_jan_kowalski,
    dyscyplina1,
    dyscyplina2,
    dyscyplina3,
    ustaw_rok,
    punkty,
    ma_byc_1,
    ma_byc_2,
    rok,
):
    ciagle_z_dyscyplinami.punkty_kbn = punkty
    ciagle_z_dyscyplinami.rok = ustaw_rok
    ciagle_z_dyscyplinami.save()
    powiel_wpisy_dyscyplin_autorow(ciagle_z_dyscyplinami, rok, ustaw_rok)

    slot = ISlot(ciagle_z_dyscyplinami)

    assert f"{slot.punkty_pkd(dyscyplina1):.4f}" == ma_byc_1
    assert f"{slot.punkty_pkd(dyscyplina2):.4f}" == ma_byc_1
    assert slot.punkty_pkd(dyscyplina3) is None

    assert f"{slot.pkd_dla_autora(autor_jan_kowalski):.4f}" == ma_byc_1
    assert f"{slot.pkd_dla_autora(autor_jan_nowak):.4f}" == ma_byc_1

    assert f"{slot.slot_dla_autora(autor_jan_kowalski):.4f}" == ma_byc_2
    assert f"{slot.slot_dla_autora(autor_jan_nowak):.4f}" == ma_byc_2
    assert slot.slot_dla_autora_z_dyscypliny(dyscyplina3) is None

    assert f"{slot.slot_dla_dyscypliny(dyscyplina1):.4f}" == ma_byc_2
    assert f"{slot.slot_dla_dyscypliny(dyscyplina2):.4f}" == ma_byc_2
    assert slot.slot_dla_dyscypliny(dyscyplina3) is None


@pytest.mark.django_db
def test_slotkalkulator_wydawnictwo_ciagle_prog3_punkty_pkd(
    ciagle_z_dyscyplinami, dyscyplina1, rok
):
    ciagle_z_dyscyplinami.rok = 2018
    ciagle_z_dyscyplinami.punkty_kbn = 5
    ciagle_z_dyscyplinami.save()

    powiel_wpisy_dyscyplin_autorow(ciagle_z_dyscyplinami, rok, 2018)

    slot = SlotKalkulator_Wydawnictwo_Ciagle_Prog3(ciagle_z_dyscyplinami)

    assert slot.punkty_pkd(dyscyplina1) == 2.5
    assert slot.slot_dla_autora_z_dyscypliny(dyscyplina1) == 0.5
    assert slot.slot_dla_dyscypliny(dyscyplina1) == 0.5

    # Zdejmij afiliacje i sprawdz czy k_przez_m wyjdzie zero
    for aut in ciagle_z_dyscyplinami.autorzy_set.all():
        aut.afiliuje = False
        Autor_Dyscyplina.objects.get_or_create(
            autor=aut.autor,
            dyscyplina_naukowa=aut.dyscyplina_naukowa,
            rok=ciagle_z_dyscyplinami.rok,
        )
        aut.save()

    slot = SlotKalkulator_Wydawnictwo_Ciagle_Prog2(ciagle_z_dyscyplinami)
    assert str(round(slot.slot_dla_dyscypliny(dyscyplina1), 4)) == "0.0000"


@pytest.mark.django_db
def test_slotkalkulator_wydawnictwo_ciagle_prog2_punkty_pkd(
    ciagle_z_dyscyplinami, dyscyplina1, rok
):
    powiel_wpisy_dyscyplin_autorow(ciagle_z_dyscyplinami, rok, 2018)
    ciagle_z_dyscyplinami.rok = 2018
    ciagle_z_dyscyplinami.punkty_kbn = 20
    ciagle_z_dyscyplinami.save()

    slot = SlotKalkulator_Wydawnictwo_Ciagle_Prog2(ciagle_z_dyscyplinami)

    assert str(round(slot.punkty_pkd(dyscyplina1), 4)) == "14.1421"
    assert str(round(slot.slot_dla_autora_z_dyscypliny(dyscyplina1), 4)) == "0.7071"
    assert str(round(slot.slot_dla_dyscypliny(dyscyplina1), 4)) == "0.7071"

    assert isinstance(slot.pierwiastek_k_przez_m(dyscyplina1), Decimal)

    # Zdejmij afiliacje i sprawdz czy k_przez_m wyjdzie zero
    for aut in ciagle_z_dyscyplinami.autorzy_set.all():
        aut.afiliuje = False
        Autor_Dyscyplina.objects.get_or_create(
            autor=aut.autor,
            dyscyplina_naukowa=aut.dyscyplina_naukowa,
            rok=ciagle_z_dyscyplinami.rok,
        )
        aut.save()

    slot = SlotKalkulator_Wydawnictwo_Ciagle_Prog2(ciagle_z_dyscyplinami)
    assert str(round(slot.slot_dla_dyscypliny(dyscyplina1), 4)) == "0.0000"


@pytest.mark.django_db
def test_ISlot_wydawnictwo_ciagle_bez_punktow_kbn(ciagle_z_dyscyplinami):
    ciagle_z_dyscyplinami.punkty_kbn = 0

    with pytest.raises(CannotAdapt, match="nie pozwalają"):
        ISlot(ciagle_z_dyscyplinami)
