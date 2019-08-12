from decimal import Decimal

import pytest

from bpp.models import TO_REDAKTOR, TO_AUTOR, Typ_Odpowiedzialnosci, Cache_Punktacja_Autora, Cache_Punktacja_Dyscypliny, \
    Charakter_Formalny
from bpp.models.sloty.core import ISlot, IPunktacjaCacher
from bpp.models.sloty.exceptions import CannotAdapt
from bpp.models.sloty.wydawnictwo_ciagle import SlotKalkulator_Wydawnictwo_Ciagle_Prog3, \
    SlotKalkulator_Wydawnictwo_Ciagle_Prog2
from bpp.models.sloty.wydawnictwo_zwarte import SlotKalkulator_Wydawnictwo_Zwarte_Prog3, \
    SlotKalkulator_Wydawnictwo_Zwarte_Prog2, SlotKalkulator_Wydawnictwo_Zwarte_Prog1


@pytest.fixture
@pytest.mark.django_db
def zwarte_z_dyscyplinami(
        wydawnictwo_zwarte,
        autor_jan_nowak,
        autor_jan_kowalski,
        jednostka,
        dyscyplina1,
        dyscyplina2,
        charaktery_formalne,
        wydawca,
        typy_odpowiedzialnosci):
    wydawnictwo_zwarte.dodaj_autora(
        autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1
    )

    wydawnictwo_zwarte.dodaj_autora(
        autor_jan_kowalski, jednostka, dyscyplina_naukowa=dyscyplina2
    )

    # domyslnie: ksiazka/autorstwo/wydawca spoza wykazu
    wydawnictwo_zwarte.punkty_kbn = 20
    wydawnictwo_zwarte.wydawca = wydawca
    wydawnictwo_zwarte.charakter_formalny = Charakter_Formalny.objects.get(skrot='KSP')
    wydawnictwo_zwarte.save()

    return wydawnictwo_zwarte


@pytest.fixture
@pytest.mark.django_db
def ciagle_z_dyscyplinami(
        wydawnictwo_ciagle,
        autor_jan_nowak,
        autor_jan_kowalski,
        jednostka,
        dyscyplina1,
        dyscyplina2,
        typy_odpowiedzialnosci):
    wydawnictwo_ciagle.dodaj_autora(
        autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1
    )

    wydawnictwo_ciagle.dodaj_autora(
        autor_jan_kowalski, jednostka, dyscyplina_naukowa=dyscyplina2
    )

    return wydawnictwo_ciagle


@pytest.mark.django_db
@pytest.mark.xfail(reason="po zrobieniu zwartych")
def test_slot_wszyscy_autorzy(zwarte_z_dyscyplinami):
    zwarte_z_dyscyplinami.rok = 2017
    zwarte_z_dyscyplinami.punkty_kbn = 20  # Tier0
    zwarte_z_dyscyplinami.save()

    slot = ISlot(zwarte_z_dyscyplinami)

    zwarte_z_dyscyplinami.calkowita_liczba_autorow = 10
    assert slot.wszyscy_autorzy() == 10
    assert slot.wszyscy_autorzy(typ_ogolny=TO_AUTOR) == 10

    zwarte_z_dyscyplinami.calkowita_liczba_autorow = None
    assert slot.wszyscy_autorzy() == 2
    assert slot.wszyscy_autorzy(TO_AUTOR) == 2
    assert slot.wszyscy_autorzy(TO_REDAKTOR) == 0

    zwarte_z_dyscyplinami.calkowita_liczba_autorow = 10
    zwarte_z_dyscyplinami.calkowita_liczba_redaktorow = 5
    assert slot.wszyscy_autorzy() == 10
    assert slot.wszyscy_autorzy(TO_AUTOR) == 10
    assert slot.wszyscy_autorzy(TO_REDAKTOR) == 5

    zwarte_z_dyscyplinami.calkowita_liczba_autorow = None
    zwarte_z_dyscyplinami.calkowita_liczba_redaktorow = None
    assert slot.wszyscy_autorzy() == 2
    assert slot.wszyscy_autorzy(TO_AUTOR) == 2
    assert slot.wszyscy_autorzy(TO_REDAKTOR) == 0

    wza = zwarte_z_dyscyplinami.autorzy_set.first()
    wza.typ_odpowiedzialnosci = Typ_Odpowiedzialnosci.objects.get(skrot="red.")
    wza.save()

    assert slot.wszyscy_autorzy() == 2
    assert slot.wszyscy_autorzy(TO_AUTOR) == 1
    assert slot.wszyscy_autorzy(TO_REDAKTOR) == 1


@pytest.mark.parametrize(
    "rekord,ustaw_rok,punkty_kbn", [
        # (pytest.lazy_fixture("wydawnictwo_zwarte"), 2017, 20),
        (pytest.lazy_fixture("wydawnictwo_ciagle"), 2017, 30)
    ]
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
        typy_odpowiedzialnosci):
    rekord.rok = ustaw_rok
    rekord.punkty_kbn = punkty_kbn
    rekord.save()

    rekord.dodaj_autora(
        autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1
    )

    rekord.dodaj_autora(
        autor_jan_kowalski, jednostka, dyscyplina_naukowa=dyscyplina2
    )

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
        dyscyplina3):
    ciagle_z_dyscyplinami.punkty_kbn = 30
    ciagle_z_dyscyplinami.rok = 2017
    ciagle_z_dyscyplinami.save()

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


@pytest.mark.django_db
@pytest.mark.parametrize("ustaw_rok,punkty,ma_byc_1,ma_byc_2", [
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

])
def test_slot_artykuly(
        ciagle_z_dyscyplinami,
        autor_jan_nowak,
        autor_jan_kowalski,
        dyscyplina1,
        dyscyplina2,
        dyscyplina3,
        ustaw_rok, punkty, ma_byc_1, ma_byc_2):
    ciagle_z_dyscyplinami.punkty_kbn = punkty
    ciagle_z_dyscyplinami.rok = ustaw_rok
    ciagle_z_dyscyplinami.save()

    slot = ISlot(ciagle_z_dyscyplinami)

    assert f"{slot.punkty_pkd(dyscyplina1):.4f}" == ma_byc_1
    assert f"{slot.punkty_pkd(dyscyplina2):.4f}" == ma_byc_1
    assert slot.punkty_pkd(dyscyplina3) == None

    assert f"{slot.pkd_dla_autora(autor_jan_kowalski):.4f}" == ma_byc_1
    assert f"{slot.pkd_dla_autora(autor_jan_nowak):.4f}" == ma_byc_1

    assert f"{slot.slot_dla_autora(autor_jan_kowalski):.4f}" == ma_byc_2
    assert f"{slot.slot_dla_autora(autor_jan_nowak):.4f}" == ma_byc_2
    assert slot.slot_dla_autora_z_dyscypliny(dyscyplina3) == None

    assert f"{slot.slot_dla_dyscypliny(dyscyplina1):.4f}" == ma_byc_2
    assert f"{slot.slot_dla_dyscypliny(dyscyplina2):.4f}" == ma_byc_2
    assert slot.slot_dla_dyscypliny(dyscyplina3) == None


@pytest.mark.django_db
def test_IPunktacjaCacher(
        ciagle_z_dyscyplinami,
        autor_jan_nowak,
        autor_jan_kowalski,
        dyscyplina1,
        dyscyplina2,
        dyscyplina3):
    ciagle_z_dyscyplinami.punkty_kbn = 30
    ciagle_z_dyscyplinami.rok = 2017
    ciagle_z_dyscyplinami.save()

    ipc = IPunktacjaCacher(ciagle_z_dyscyplinami)
    assert ipc.canAdapt()

    ipc.rebuildEntries()

    assert Cache_Punktacja_Dyscypliny.objects.count() == 2
    assert Cache_Punktacja_Autora.objects.count() == 2


@pytest.mark.django_db
def test_slotkalkulator_wydawnictwo_ciagle_prog3_punkty_pkd(
        ciagle_z_dyscyplinami, dyscyplina1):
    ciagle_z_dyscyplinami.rok = 2018
    ciagle_z_dyscyplinami.punkty_kbn = 5
    ciagle_z_dyscyplinami.save()

    slot = SlotKalkulator_Wydawnictwo_Ciagle_Prog3(ciagle_z_dyscyplinami)

    assert slot.punkty_pkd(dyscyplina1) == 2.5
    assert slot.slot_dla_autora_z_dyscypliny(dyscyplina1) == 0.5
    assert slot.slot_dla_dyscypliny(dyscyplina1) == 0.5


@pytest.mark.django_db
def test_slotkalkulator_wydawnictwo_ciagle_prog2_punkty_pkd(
        ciagle_z_dyscyplinami, dyscyplina1):
    ciagle_z_dyscyplinami.rok = 2018
    ciagle_z_dyscyplinami.punkty_kbn = 20
    ciagle_z_dyscyplinami.save()

    slot = SlotKalkulator_Wydawnictwo_Ciagle_Prog2(ciagle_z_dyscyplinami)

    assert str(round(slot.punkty_pkd(dyscyplina1), 4)) == "14.1421"
    assert str(round(slot.slot_dla_autora_z_dyscypliny(dyscyplina1), 4)) == "0.7071"
    assert str(round(slot.slot_dla_dyscypliny(dyscyplina1), 4)) == "0.7071"

    assert type(slot.pierwiastek_k_przez_m(dyscyplina1)) == Decimal


@pytest.mark.django_db
def test_ISlot_wydawnictwo_zwarte_zakres_lat_nie_ten(zwarte_z_dyscyplinami):
    zwarte_z_dyscyplinami.rok = 2016

    with pytest.raises(CannotAdapt):
        ISlot(zwarte_z_dyscyplinami)

    zwarte_z_dyscyplinami.rok = 2021

    with pytest.raises(CannotAdapt):
        ISlot(zwarte_z_dyscyplinami)

    zwarte_z_dyscyplinami.rok = 2020
    ISlot(zwarte_z_dyscyplinami)


@pytest.mark.django_db
def test_ISlot_wydawnictwo_zwarte_redakcja_i_autorstwo(zwarte_z_dyscyplinami):
    a1 = zwarte_z_dyscyplinami.autorzy_set.first()
    a1.typ_odpowiedzialnosci = Typ_Odpowiedzialnosci.objects.get(skrot="red.")
    a1.save()

    with pytest.raises(CannotAdapt, match="ma jednocześnie"):
        ISlot(zwarte_z_dyscyplinami)


@pytest.mark.django_db
def test_ISlot_wydawnictwo_zwarte_bez_red_bez_aut(zwarte_z_dyscyplinami):
    zwarte_z_dyscyplinami.autorzy_set.all().delete()

    with pytest.raises(CannotAdapt, match="nie posiada"):
        ISlot(zwarte_z_dyscyplinami)


@pytest.mark.django_db
def test_ISlot_wydawnictwo_Zwarte_nie_te_punkty(zwarte_z_dyscyplinami):
    zwarte_z_dyscyplinami.punkty_kbn = 12345
    with pytest.raises(CannotAdapt, match="nie można dopasować do żadnej z grup"):
        ISlot(zwarte_z_dyscyplinami)


@pytest.mark.django_db
def test_ISlot_wydawnictwo_zwarte_tier3(zwarte_z_dyscyplinami):
    i = ISlot(zwarte_z_dyscyplinami)
    assert isinstance(i, SlotKalkulator_Wydawnictwo_Zwarte_Prog3)


@pytest.mark.django_db
def test_ISlot_wydawnictwo_zwarte_tier2(zwarte_z_dyscyplinami, wydawca, rok):
    wydawca.poziom_wydawcy_set.create(rok=rok, poziom=1)
    zwarte_z_dyscyplinami.punkty_kbn = 80
    i = ISlot(zwarte_z_dyscyplinami)
    assert isinstance(i, SlotKalkulator_Wydawnictwo_Zwarte_Prog2)


@pytest.mark.django_db
def test_ISlot_wydawnictwo_zwarte_tier1(zwarte_z_dyscyplinami, wydawca, rok):
    wydawca.poziom_wydawcy_set.create(rok=rok, poziom=2)
    zwarte_z_dyscyplinami.punkty_kbn = 200
    i = ISlot(zwarte_z_dyscyplinami)
    assert isinstance(i, SlotKalkulator_Wydawnictwo_Zwarte_Prog1)
