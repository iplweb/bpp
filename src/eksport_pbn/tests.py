# -*- encoding: utf-8 -*-

from __future__ import unicode_literals

from datetime import datetime, timedelta

from django.core.urlresolvers import reverse
from model_mommy import mommy

from bpp.models.struktura import Wydzial
from eksport_pbn.models import PlikEksportuPBN, DATE_CREATED_ON
from eksport_pbn.tasks import eksport_pbn, id_zwartych, id_ciaglych, remove_old_eksport_pbn_files


def test_wybor(app, wydzial):
    page = app.get(reverse('eksport_pbn:zamow'))
    assert '2013' in page.content


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


def test_serializuj_pbn_ciagle(wydawnictwo_ciagle_z_autorem, wydzial):
    wydawnictwo_ciagle_z_autorem.eksport_pbn_serializuj(wydzial)


def test_serializuj_pbn_zwarte(wydawnictwo_zwarte_z_autorem, wydzial):
    wydawnictwo_zwarte_z_autorem.eksport_pbn_serializuj(wydzial)


def test_eksport_pbn(normal_django_user, jednostka, autor_jan_kowalski, wydawnictwo_ciagle, wydawnictwo_zwarte, rok):
    assert PlikEksportuPBN.objects.all().count() == 0

    autor_jan_kowalski.dodaj_jednostke(jednostka=jednostka)

    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)

    assert wydawnictwo_zwarte.charakter_formalny != wydawnictwo_ciagle.charakter_formalny

    cf = wydawnictwo_ciagle.charakter_formalny
    cf.artykul_pbn = True
    cf.ksiazka_pbn = cf.rozdzial_pbn = False
    cf.save()

    cf = wydawnictwo_zwarte.charakter_formalny
    cf.artykul_pbn = cf.rozdzial_pbn = False
    cf.ksiazka_pbn = True
    cf.save()

    obj = PlikEksportuPBN.objects.create(
            owner=normal_django_user,
            wydzial=jednostka.wydzial,
            od_roku=rok, do_roku=rok
    )

    eksport_pbn(obj.pk)

    assert PlikEksportuPBN.objects.all().count() == 1


def test_remove_old_eksport_files(db):
    mommy.make(PlikEksportuPBN, created_on=datetime.now())
    e2 = mommy.make(PlikEksportuPBN)
    e2.created_on = datetime.now() - timedelta(days=15)
    e2.save()

    assert PlikEksportuPBN.objects.all().count() == 2

    remove_old_eksport_pbn_files()

    assert PlikEksportuPBN.objects.all().count() == 1


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


def test_submit_report_form(admin_app, wydzial):
    page = admin_app.get(reverse("eksport_pbn:zamow"))
    page.form['wydzial'] = wydzial.pk
    res = page.form.submit().maybe_follow()
    assert res.status_code == 200


def test_submit_report_form_validation_data_od_do(admin_app, wydzial):
    page = admin_app.get(reverse("eksport_pbn:zamow"))
    page.form['wydzial'] = wydzial.pk
    page.form['od_daty'] = '2010-01-01'
    page.form['do_daty'] = '2009-01-01'
    res = page.form.submit()
    assert "Wartość w polu &#39;Od daty&#39; musi" in res.content.decode('utf-8')


def test_submit_report_form_validation_rok_od_do(admin_app, wydzial):
    page = admin_app.get(reverse("eksport_pbn:zamow"))
    page.form['wydzial'] = wydzial.pk
    page.form['od_roku'] = '2015'
    page.form['do_roku'] = '2014'
    res = page.form.submit()
    assert "Wartość w polu &#39;Od roku&#39; musi" in res.content.decode('utf-8')



def test_submit_report_form_validation_artykuly_ksiazki(admin_app, wydzial):
    page = admin_app.get(reverse("eksport_pbn:zamow"))
    page.form['wydzial'] = wydzial.pk
    page.form['artykuly'] = False
    page.form['ksiazki'] = False
    page.form['rozdzialy'] = False
    res = page.form.submit()
    assert "Wybierz przynajmniej jedną" in res.content.decode('utf-8')