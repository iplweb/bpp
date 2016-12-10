# -*- encoding: utf-8 -*-

from __future__ import unicode_literals
from __future__ import unicode_literals

from datetime import datetime, timedelta

from model_mommy import mommy

from eksport_pbn.models import PlikEksportuPBN, DATE_CREATED_ON
from eksport_pbn.tasks import id_zwartych, id_ciaglych


def test_id_zwartych(wydawnictwo_zwarte_z_autorem, wydzial, rok):
    cf = wydawnictwo_zwarte_z_autorem.charakter_formalny

    cf.ksiazka_pbn = True
    cf.save()

    l = id_zwartych(wydzial, rok, rok, True, True)
    assert len(list(l)) == 1


def test_id_ciaglych(wydawnictwo_ciagle_z_autorem, wydzial, rok):
    cf = wydawnictwo_ciagle_z_autorem.charakter_formalny

    cf.artykul_pbn = True
    cf.save()

    l = id_ciaglych(wydzial, rok, rok)
    assert l.count() == 1


def test_z_datami(jednostka, autor_jan_kowalski, wydawnictwo_ciagle, wydawnictwo_zwarte, rok):
    autor_jan_kowalski.dodaj_jednostke(jednostka=jednostka)
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)

    rok = wydawnictwo_ciagle.rok

    assert list(id_ciaglych(jednostka.wydzial, od_roku=rok, do_roku=rok, rodzaj_daty=DATE_CREATED_ON,
                            od_daty=(datetime.now() + timedelta(days=20)).date())) == []
    assert list(id_zwartych(jednostka.wydzial, od_roku=rok, do_roku=rok, ksiazki=True, rozdzialy=True,
                            rodzaj_daty=DATE_CREATED_ON, do_daty=(datetime.now() + timedelta(days=20)).date())) == []

    assert list(id_ciaglych(jednostka.wydzial, od_roku=rok, do_roku=rok, rodzaj_daty=DATE_CREATED_ON,
                            do_daty=(datetime.now() + timedelta(days=20)).date())) == []
    assert list(id_zwartych(jednostka.wydzial, od_roku=rok, do_roku=rok, ksiazki=True, rozdzialy=True,
                            rodzaj_daty=DATE_CREATED_ON, do_daty=(datetime.now() + timedelta(days=20)).date())) == []


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
