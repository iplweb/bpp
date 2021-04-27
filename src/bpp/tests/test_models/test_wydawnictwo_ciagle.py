# -*- encoding: utf-8 -*-


import pytest

from bpp.admin.helpers import MODEL_PUNKTOWANY, MODEL_PUNKTOWANY_KOMISJA_CENTRALNA
from bpp.models import RODZAJ_PBN_ARTYKUL
from bpp.models.openaccess import Licencja_OpenAccess
from bpp.models.system import Status_Korekty


@pytest.mark.django_db
def test_models_wydawnictwo_ciagle_dirty_fields_ostatnio_zmieniony_dla_pbn(
    wydawnictwo_ciagle,
    wydawnictwo_zwarte,
    autor_jan_nowak,
    jednostka,
    typy_odpowiedzialnosci,
):
    Licencja_OpenAccess.objects.create(nazwa="lic 1 ", skrot="l1")
    Licencja_OpenAccess.objects.create(nazwa="lic 2 ", skrot="l2")

    # Licencje muszą być w bazie, jakiekolwiek
    assert (
        Licencja_OpenAccess.objects.all().first()
        != Licencja_OpenAccess.objects.all().last()
    )

    for wyd in wydawnictwo_ciagle, wydawnictwo_zwarte:
        wyd.openaccess_licencja = Licencja_OpenAccess.objects.all().first()
        wyd.save()

        ost_zm_pbn = wyd.ostatnio_zmieniony_dla_pbn

        wyd.status = Status_Korekty.objects.get(nazwa="w trakcie korekty")
        wyd.save()
        assert ost_zm_pbn == wyd.ostatnio_zmieniony_dla_pbn

        wyd.status = Status_Korekty.objects.get(nazwa="po korekcie")
        wyd.save()
        assert ost_zm_pbn == wyd.ostatnio_zmieniony_dla_pbn

        for fld in (
            MODEL_PUNKTOWANY_KOMISJA_CENTRALNA + MODEL_PUNKTOWANY + ("adnotacje",)
        ):
            if fld == "weryfikacja_punktacji":
                continue
            setattr(wyd, fld, 123)
            wyd.save()
            assert ost_zm_pbn == wyd.ostatnio_zmieniony_dla_pbn
            # time.sleep(0.5)

        wyd.tytul_oryginalny = "1234 test zmian"
        wyd.save()

        try:
            assert ost_zm_pbn != wyd.ostatnio_zmieniony_dla_pbn
        except TypeError:
            pass  # TypeError: can't compare offset-naive and offset-aware datetimes

        ost_zm_pbn = wyd.ostatnio_zmieniony_dla_pbn

        aj = wyd.dodaj_autora(autor_jan_nowak, jednostka)
        wyd.refresh_from_db()
        assert ost_zm_pbn != wyd.ostatnio_zmieniony_dla_pbn

        ost_zm_pbn = wyd.ostatnio_zmieniony_dla_pbn

        aj.delete()
        wyd.refresh_from_db()
        assert ost_zm_pbn != wyd.ostatnio_zmieniony_dla_pbn

        # Test na foreign keys
        ost_zm_pbn = wyd.ostatnio_zmieniony_dla_pbn

        assert wyd.openaccess_licencja.pk != Licencja_OpenAccess.objects.all().last().pk
        wyd.openaccess_licencja = Licencja_OpenAccess.objects.all().last()
        wyd.save()

        wyd.refresh_from_db()
        assert ost_zm_pbn != wyd.ostatnio_zmieniony_dla_pbn


@pytest.mark.django_db
@pytest.mark.parametrize(
    "informacje,expected",
    [("bez sensu", None), ("2016 vol. 5 nr 10", "5"), ("2019 Bd 4 nr. 3 test", "4")],
)
def test_eksport_pbn_get_volume(informacje, expected, wydawnictwo_ciagle):
    wydawnictwo_ciagle.informacje = informacje
    assert wydawnictwo_ciagle.numer_tomu() == expected


@pytest.mark.django_db
def test_eksport_pbn_volume(wydawnictwo_ciagle):
    wydawnictwo_ciagle.informacje = "bez sensu"
    assert wydawnictwo_ciagle.numer_tomu() is None

    wydawnictwo_ciagle.informacje = "2016 vol 4"
    assert wydawnictwo_ciagle.numer_tomu() == "4"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "informacje,expected",
    [
        ("bez sensu", None),
        ("2016 vol. 5 nr 10", "10"),
        ("2019 Bd 4 nr. 3 test", "3 test"),
        ("2019 Bd 4 nr 3 test", "3 test"),
        ("2019 Bd 4 z. 3 test", "3 test"),
        ("2019 Bd 4 h. 3 test", "3 test"),
        ("2019 Bd 4 iss. 311 test", "311 test"),
    ],
)
def test_eksport_pbn_get_issue(informacje, expected, wydawnictwo_ciagle):
    wydawnictwo_ciagle.informacje = informacje
    assert wydawnictwo_ciagle.numer_wydania() == expected


def test_punktacja_zrodla(wydawnictwo_ciagle):
    assert wydawnictwo_ciagle.punktacja_zrodla() is None

    z = wydawnictwo_ciagle.zrodlo
    z.punktacja_zrodla_set.create(rok=1990, impact_factor=100)

    assert wydawnictwo_ciagle.punktacja_zrodla() is None

    z.punktacja_zrodla_set.create(rok=wydawnictwo_ciagle.rok, impact_factor=37)
    assert wydawnictwo_ciagle.punktacja_zrodla().impact_factor == 37


def test_Wydawnictwo_Ciagle_pbn_get_json(wydawnictwo_ciagle):
    cf = wydawnictwo_ciagle.charakter_formalny
    cf.rodzaj_pbn = RODZAJ_PBN_ARTYKUL
    cf.save()

    wydawnictwo_ciagle.doi = "123;.123/doi"
    assert wydawnictwo_ciagle.pbn_get_json()
