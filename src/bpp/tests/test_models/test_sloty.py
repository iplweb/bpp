import pytest

from bpp.models import TO_REDAKTOR, TO_AUTOR, Typ_Odpowiedzialnosci, Cache_Punktacja_Autora, Cache_Punktacja_Dyscypliny
from bpp.models.sloty.core import ISlot, IPunktacjaCacher


@pytest.fixture
@pytest.mark.django_db
def zwarte_z_dyscyplinami(
        wydawnictwo_zwarte,
        autor_jan_nowak,
        autor_jan_kowalski,
        jednostka,
        dyscyplina1,
        dyscyplina2,
        typy_odpowiedzialnosci):
    wydawnictwo_zwarte.dodaj_autora(
        autor_jan_nowak, jednostka, dyscyplina_naukowa=dyscyplina1
    )

    wydawnictwo_zwarte.dodaj_autora(
        autor_jan_kowalski, jednostka, dyscyplina_naukowa=dyscyplina2
    )

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
        (pytest.lazy_fixture("wydawnictwo_zwarte"), 2017, 20),
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

    assert slot.autorzy_z_dyscypliny(dyscyplina1).count() == 1
    assert slot.autorzy_z_dyscypliny(dyscyplina2).count() == 1
    assert slot.autorzy_z_dyscypliny(dyscyplina3).count() == 0

    assert slot.autorzy_z_dyscypliny(dyscyplina1, TO_AUTOR).count() == 1
    assert slot.autorzy_z_dyscypliny(dyscyplina2, TO_AUTOR).count() == 1
    assert slot.autorzy_z_dyscypliny(dyscyplina3, TO_AUTOR).count() == 0

    assert slot.autorzy_z_dyscypliny(dyscyplina1, TO_REDAKTOR).count() == 0
    assert slot.autorzy_z_dyscypliny(dyscyplina2, TO_REDAKTOR).count() == 0
    assert slot.autorzy_z_dyscypliny(dyscyplina3, TO_REDAKTOR).count() == 0



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

    ciagle_z_dyscyplinami.punkty_kbn =30
    ciagle_z_dyscyplinami.rok = 2017
    ciagle_z_dyscyplinami.save()

    ipc = IPunktacjaCacher(ciagle_z_dyscyplinami)
    assert ipc.canAdapt()

    ipc.rebuildEntries()

    assert Cache_Punktacja_Dyscypliny.objects.count() == 2
    assert Cache_Punktacja_Autora.objects.count() == 2
