# -*- encoding: utf-8 -*-


from datetime import datetime, timedelta

import pytest
from model_mommy import mommy

from bpp.models import TO_REDAKTOR, const
from bpp.models.autor import Autor
from bpp.models.struktura import Jednostka, Uczelnia, Wydzial
from bpp.models.system import Charakter_Formalny, Typ_Odpowiedzialnosci
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte
from eksport_pbn.models import DATE_CREATED_ON, DATE_UPDATED_ON_PBN, PlikEksportuPBN
from eksport_pbn.tasks import id_ciaglych, id_zwartych


@pytest.mark.django_db
def test_id_zwartych(wydawnictwo_zwarte_z_autorem, rok):
    """
    :type wydawnictwo_zwarte_z_autorem: bpp.models.Wydawnictwo_Zwarte
    """
    wydawnictwo_zwarte_z_autorem.liczba_znakow_wydawniczych = 240000
    wydawnictwo_zwarte_z_autorem.punkty_kbn = 6
    wydawnictwo_zwarte_z_autorem.save()

    cf = wydawnictwo_zwarte_z_autorem.charakter_formalny
    cf.liczba_znakow_wydawniczych = 240000
    cf.punkty_kbn = 6
    cf.rodzaj_pbn = const.RODZAJ_PBN_KSIAZKA
    cf.save()

    res = id_zwartych(rok, rok, True, True)
    assert len(list(res)) == 1


@pytest.mark.django_db
def test_id_ciaglych(wydawnictwo_ciagle_z_autorem, rok):
    cf = wydawnictwo_ciagle_z_autorem.charakter_formalny
    cf.rodzaj_pbn = const.RODZAJ_PBN_ARTYKUL
    cf.save()

    tk = wydawnictwo_ciagle_z_autorem.typ_kbn
    tk.artykul_pbn = True
    tk.save()

    res = id_ciaglych(rok, rok)
    assert res.count() == 1


def test_z_datami(
    jednostka, autor_jan_kowalski, wydawnictwo_ciagle, wydawnictwo_zwarte, rok
):
    cf = wydawnictwo_ciagle.charakter_formalny
    cf.rodzaj_pbn = const.RODZAJ_PBN_ARTYKUL
    cf.save()

    tk = wydawnictwo_ciagle.typ_kbn
    tk.artykul_pbn = True
    tk.save()

    autor_jan_kowalski.dodaj_jednostke(jednostka=jednostka)
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)

    rok = wydawnictwo_ciagle.rok

    assert (
        list(
            id_ciaglych(
                od_roku=rok,
                do_roku=rok,
                rodzaj_daty=DATE_CREATED_ON,
                od_daty=(datetime.now() + timedelta(days=20)).date(),
            )
        )
        == []
    )

    assert (
        list(
            id_zwartych(
                od_roku=rok,
                do_roku=rok,
                ksiazki=True,
                rozdzialy=True,
                rodzaj_daty=DATE_CREATED_ON,
                do_daty=(datetime.now() + timedelta(days=20)).date(),
            )
        )
        == []
    )

    assert (
        list(
            id_ciaglych(
                od_roku=rok,
                do_roku=rok,
                rodzaj_daty=DATE_CREATED_ON,
                od_daty=(datetime.now() + timedelta(days=20)).date(),
            )
        )
        == []
    )

    assert (
        list(
            id_zwartych(
                od_roku=rok,
                do_roku=rok,
                ksiazki=True,
                rozdzialy=True,
                rodzaj_daty=DATE_CREATED_ON,
                do_daty=(datetime.now() + timedelta(days=20)).date(),
            )
        )
        == []
    )


def test_z_datami_2(db):
    d = datetime.now().date()

    p = mommy.make(PlikEksportuPBN, rodzaj_daty=DATE_CREATED_ON)

    p.od_daty = d
    p.do_daty = None
    s = p.get_fn()
    assert str(d).replace("-", "_") in s

    p.do_daty = d
    s = p.get_fn()
    assert str(d).replace("-", "_") in s


@pytest.mark.django_db
def test_ta_sama_data_id_ciaglych(
    jednostka, autor_jan_kowalski, wydawnictwo_ciagle, rok, settings
):
    settings.TIME_ZONE = "UTC"

    cf = wydawnictwo_ciagle.charakter_formalny
    cf.rodzaj_pbn = const.RODZAJ_PBN_ARTYKUL
    cf.save()

    tk = wydawnictwo_ciagle.typ_kbn
    tk.artykul_pbn = True
    tk.save()

    autor_jan_kowalski.dodaj_jednostke(jednostka=jednostka)
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)

    d = wydawnictwo_ciagle.ostatnio_zmieniony_dla_pbn

    od_daty = d.date()
    do_daty = d.date()

    res = id_ciaglych(
        od_roku=rok,
        do_roku=rok,
        rodzaj_daty=DATE_UPDATED_ON_PBN,
        od_daty=od_daty,
        do_daty=do_daty,
    )

    assert wydawnictwo_ciagle.pk in list(res)


@pytest.mark.django_db
def test_ta_sama_data_id_zwartych(
    jednostka, autor_jan_kowalski, wydawnictwo_zwarte, rok, settings
):
    settings.TIME_ZONE = "UTC"

    cf = wydawnictwo_zwarte.charakter_formalny
    cf.rodzaj_pbn = const.RODZAJ_PBN_KSIAZKA
    cf.save()

    wydawnictwo_zwarte.punkty_kbn = 10
    wydawnictwo_zwarte.save()

    autor_jan_kowalski.dodaj_jednostke(jednostka=jednostka)
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)

    d = wydawnictwo_zwarte.ostatnio_zmieniony_dla_pbn

    od_daty = d.date()
    do_daty = d.date()

    res = id_zwartych(
        od_roku=rok,
        do_roku=rok,
        ksiazki=True,
        rozdzialy=False,
        rodzaj_daty=DATE_UPDATED_ON_PBN,
        od_daty=od_daty,
        do_daty=do_daty,
    )

    assert wydawnictwo_zwarte.pk in list(res)
