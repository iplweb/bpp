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
def test_id_zwartych(wydawnictwo_zwarte_z_autorem, wydzial, rok):
    """
    :type wydawnictwo_zwarte_z_autorem: bpp.models.Wydawnictwo_Zwarte
    """
    wydawnictwo_zwarte_z_autorem.liczba_znakow_wydawniczych = 240000
    wydawnictwo_zwarte_z_autorem.punkty_kbn = 5
    wydawnictwo_zwarte_z_autorem.save()

    cf = wydawnictwo_zwarte_z_autorem.charakter_formalny
    cf.liczba_znakow_wydawniczych = 240000
    cf.punkty_kbn = 4
    cf.rodzaj_pbn = const.RODZAJ_PBN_KSIAZKA
    cf.save()

    res = id_zwartych(wydzial, rok, rok, True, True)
    assert len(list(res)) == 1


@pytest.mark.django_db
def test_id_zwartych_gdy_jest_ksiazka_z_w1_ale_rozdzialy_ma_w_w2(charaktery_formalne):
    """
    Książka "nadrzędna" redagowana przez autora z W1 ma się NIE znaleźć w eksporcie dla W2
    jeżeli w przypisanych rozdziałach jest rozdział opracowany dla W2.
    :return:
    """

    chf_ksp = Charakter_Formalny.objects.get(skrot="KSP")
    chf_roz = Charakter_Formalny.objects.get(skrot="ROZ")

    u = mommy.make(Uczelnia)

    w1 = mommy.make(Wydzial, uczelnia=u)
    w2 = mommy.make(Wydzial, uczelnia=u)

    a1 = mommy.make(Autor, imiona="Jan", nazwisko="Kowalski")
    a2 = mommy.make(Autor, imiona="Stefan", nazwisko="Nowak")

    j1 = mommy.make(Jednostka, wydzial=w1, uczelnia=u)
    j2 = mommy.make(Jednostka, wydzial=w2, uczelnia=u)

    wz_root = mommy.make(
        Wydawnictwo_Zwarte,
        charakter_formalny=chf_ksp,
        szczegoly="s. 123",
        calkowita_liczba_autorow=50,
        rok=2015,
        liczba_znakow_wydawniczych=240000,
        punkty_kbn=5,
    )
    wz_child1 = mommy.make(
        Wydawnictwo_Zwarte,
        wydawnictwo_nadrzedne=wz_root,
        charakter_formalny=chf_roz,
        szczegoly="s. 10-15",
        rok=2015,
        liczba_znakow_wydawniczych=5,
        punkty_kbn=10,
    )
    wz_child2 = mommy.make(
        Wydawnictwo_Zwarte,
        wydawnictwo_nadrzedne=wz_root,
        charakter_formalny=chf_roz,
        szczegoly="s. 10-15",
        rok=2015,
        liczba_znakow_wydawniczych=5,
        punkty_kbn=10,
    )

    Typ_Odpowiedzialnosci.objects.get_or_create(skrot="aut.", nazwa="autor")

    Typ_Odpowiedzialnosci.objects.get_or_create(
        skrot="red.", nazwa="redaktor", typ_ogolny=TO_REDAKTOR
    )

    wz_root.dodaj_autora(a1, j1, typ_odpowiedzialnosci_skrot="red.")
    wz_child1.dodaj_autora(a2, j2, typ_odpowiedzialnosci_skrot="aut.")
    wz_child2.dodaj_autora(a1, j2, typ_odpowiedzialnosci_skrot="aut.")

    assert wz_root.pk in list(id_zwartych(w1, 2015, 2015, True, True))
    assert wz_child1.pk not in list(id_zwartych(w1, 2015, 2015, True, True))
    assert wz_child2.pk not in list(id_zwartych(w1, 2015, 2015, True, True))

    assert wz_root.pk not in list(id_zwartych(w2, 2015, 2015, True, True))
    assert wz_child1.pk in list(id_zwartych(w2, 2015, 2015, True, True))
    assert wz_child2.pk in list(id_zwartych(w2, 2015, 2015, True, True))


@pytest.mark.django_db
def test_id_ciaglych(wydawnictwo_ciagle_z_autorem, wydzial, rok):
    cf = wydawnictwo_ciagle_z_autorem.charakter_formalny
    cf.rodzaj_pbn = const.RODZAJ_PBN_ARTYKUL
    cf.save()

    tk = wydawnictwo_ciagle_z_autorem.typ_kbn
    tk.artykul_pbn = True
    tk.save()

    res = id_ciaglych(wydzial, rok, rok)
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
                jednostka.wydzial,
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
                jednostka.wydzial,
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
                jednostka.wydzial,
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
                jednostka.wydzial,
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
        jednostka.wydzial,
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
        jednostka.wydzial,
        od_roku=rok,
        do_roku=rok,
        ksiazki=True,
        rozdzialy=False,
        rodzaj_daty=DATE_UPDATED_ON_PBN,
        od_daty=od_daty,
        do_daty=do_daty,
    )

    assert wydawnictwo_zwarte.pk in list(res)
