from decimal import Decimal

import pytest

from django.contrib.contenttypes.models import ContentType

from bpp.const import PBN_LATA, TO_AUTOR, TO_REDAKTOR
from bpp.models import (
    Autor_Dyscyplina,
    Cache_Punktacja_Autora,
    Cache_Punktacja_Dyscypliny,
    Rekord,
    Typ_KBN,
    Typ_Odpowiedzialnosci,
    Uczelnia,
)
from bpp.models.sloty.core import IPunktacjaCacher, ISlot
from bpp.models.sloty.exceptions import CannotAdapt
from bpp.models.sloty.wydawnictwo_ciagle import (
    SlotKalkulator_Wydawnictwo_Ciagle_Prog2,
    SlotKalkulator_Wydawnictwo_Ciagle_Prog3,
)
from bpp.models.sloty.wydawnictwo_zwarte import (
    SlotKalkulator_Wydawnictwo_Zwarte_Prog1,
    SlotKalkulator_Wydawnictwo_Zwarte_Prog2,
    SlotKalkulator_Wydawnictwo_Zwarte_Prog3,
)


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
def test_IPunktacjaCacher(
    ciagle_z_dyscyplinami,
    denorms,
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

    denorms.flush()

    ipc = IPunktacjaCacher(ciagle_z_dyscyplinami)
    assert ipc.canAdapt()

    ipc.removeEntries()
    ipc.rebuildEntries()

    assert Cache_Punktacja_Dyscypliny.objects.count() == 2
    assert Cache_Punktacja_Autora.objects.count() == 2


@pytest.mark.django_db
def test_IPunktacjaCacher_brak_afiliacji(
    ciagle_z_dyscyplinami,
    autor_jan_nowak,
    autor_jan_kowalski,
    dyscyplina1,
    dyscyplina2,
    dyscyplina3,
):
    ciagle_z_dyscyplinami.punkty_kbn = 30
    ciagle_z_dyscyplinami.rok = 2017
    ciagle_z_dyscyplinami.save()

    ciagle_z_dyscyplinami.autorzy_set.update(afiliuje=False)

    ipc = IPunktacjaCacher(ciagle_z_dyscyplinami)
    assert ipc.canAdapt()
    ipc.removeEntries()
    ipc.rebuildEntries()

    assert Cache_Punktacja_Dyscypliny.objects.count() == 0
    assert Cache_Punktacja_Autora.objects.count() == 0


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


def powiel_wpisy_dyscyplin_autorow(wydawnictwo, rok_z, rok_do):
    for wca in wydawnictwo.autorzy_set.all():
        ad = wca.autor.autor_dyscyplina_set.get(rok=rok_z)
        ad.pk = None
        ad.rok = rok_do
        ad.save()


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


@pytest.mark.django_db
def test_ISlot_wydawnictwo_ciagle_bez_punktow_kbn(ciagle_z_dyscyplinami):
    ciagle_z_dyscyplinami.punkty_kbn = 0

    with pytest.raises(CannotAdapt, match="nie pozwalają"):
        ISlot(ciagle_z_dyscyplinami)


@pytest.mark.django_db
def test_cache_slotow_kasowanie_wpisow_przy_zmianie_pk_ciagle(
    ciagle_z_dyscyplinami, denorms, rok
):
    ciagle_z_dyscyplinami.punkty_kbn = 30
    ciagle_z_dyscyplinami.rok = 2017
    ciagle_z_dyscyplinami.save()

    powiel_wpisy_dyscyplin_autorow(ciagle_z_dyscyplinami, rok, 2017)

    assert ISlot(ciagle_z_dyscyplinami) is not None

    denorms.flush()

    ctype = ContentType.objects.get_for_model(ciagle_z_dyscyplinami).pk
    assert (
        Cache_Punktacja_Autora.objects.filter(
            rekord_id=[ctype, ciagle_z_dyscyplinami.pk]
        ).count()
        == 2
    )

    ciagle_z_dyscyplinami.punkty_kbn = 0
    ciagle_z_dyscyplinami.save()

    denorms.flush()
    assert (
        Cache_Punktacja_Autora.objects.filter(
            rekord_id=[ctype, ciagle_z_dyscyplinami.pk]
        ).count()
        == 0
    )


@pytest.mark.django_db
def test_cache_slotow_kasowanie_wpisow_przy_zmianie_pk_zwarte(
    zwarte_z_dyscyplinami, denorms, rok
):
    zwarte_z_dyscyplinami.punkty_kbn = 20
    zwarte_z_dyscyplinami.rok = 2017
    zwarte_z_dyscyplinami.save()

    powiel_wpisy_dyscyplin_autorow(zwarte_z_dyscyplinami, rok, 2017)

    assert ISlot(zwarte_z_dyscyplinami) is not None

    denorms.flush()

    ctype = ContentType.objects.get_for_model(zwarte_z_dyscyplinami).pk
    assert (
        Cache_Punktacja_Autora.objects.filter(
            rekord_id=[ctype, zwarte_z_dyscyplinami.pk]
        ).count()
        == 2
    )

    zwarte_z_dyscyplinami.punkty_kbn = 0
    zwarte_z_dyscyplinami.save()

    denorms.flush()

    assert (
        Cache_Punktacja_Autora.objects.filter(
            rekord_id=[ctype, zwarte_z_dyscyplinami.pk]
        ).count()
        == 0
    )


@pytest.mark.django_db
def test_sloty_prace_wieloosrodkowe(zwarte_z_dyscyplinami, typy_kbn):
    zwarte_z_dyscyplinami.typ_kbn = Typ_KBN.objects.get(skrot="PW")
    zwarte_z_dyscyplinami.save()

    with pytest.raises(CannotAdapt, match="dla prac wielo"):
        ISlot(zwarte_z_dyscyplinami)


@pytest.mark.django_db
def test_ISlot_patent(patent):
    with pytest.raises(CannotAdapt):
        ISlot(patent)


@pytest.mark.parametrize("akcja", ["wszystko", None])
@pytest.mark.django_db
def test_autor_Autor_zbieraj_sloty(zwarte_z_dyscyplinami, akcja, denorms, rok):
    zwarte_z_dyscyplinami.punkty_kbn = 20
    zwarte_z_dyscyplinami.rok = 2017
    zwarte_z_dyscyplinami.save()
    powiel_wpisy_dyscyplin_autorow(zwarte_z_dyscyplinami, rok, 2017)

    denorms.flush()

    a = zwarte_z_dyscyplinami.autorzy_set.first().autor
    res = a.zbieraj_sloty(
        1, zwarte_z_dyscyplinami.rok, zwarte_z_dyscyplinami.rok, akcja=akcja
    )
    assert res == (
        10.0,
        [
            Rekord.objects.get_for_model(zwarte_z_dyscyplinami)
            .cache_punktacja_autora_query_set.first()
            .pk
        ],
        0.5,
    )


@pytest.mark.django_db
def test_ISlot_ukryty_status_nie_licz_punktow(
    zwarte_z_dyscyplinami, przed_korekta, po_korekcie, uczelnia
):
    zwarte_z_dyscyplinami.punkty_kbn = 20
    zwarte_z_dyscyplinami.rok = 2017

    zwarte_z_dyscyplinami.status_korekty = przed_korekta
    zwarte_z_dyscyplinami.save()

    Uczelnia.objects.get_default().ukryj_status_korekty_set.create(
        status_korekty=przed_korekta
    )

    with pytest.raises(CannotAdapt):
        ISlot(zwarte_z_dyscyplinami)

    zwarte_z_dyscyplinami.status_korekty = po_korekcie
    zwarte_z_dyscyplinami.save()

    ISlot(zwarte_z_dyscyplinami)
