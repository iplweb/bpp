from datetime import datetime
from django.core.urlresolvers import reverse
import pytest
from eksport_pbn.models import PlikEksportuPBN
from eksport_pbn.tasks import eksport_pbn, id_zwartych, id_ciaglych


def test_wybor(preauth_webtest_app, wydzial):
    page = preauth_webtest_app.get(reverse('eksport_pbn:wybor_wydzialu'))
    assert '2013' in page.content


def test_generuj(preauth_webtest_app, wydzial):
    page = preauth_webtest_app.get(reverse('eksport_pbn:generuj', args=(wydzial.pk, 2013)))
    assert page.status_code == 200


def test_id_zwartych(wydawnictwo_zwarte_z_autorem, wydzial, rok):
    l = id_zwartych(wydzial, rok)
    assert l.count() == 1


def test_id_ciaglych(wydawnictwo_ciagle_z_autorem, wydzial, rok):
    l = id_ciaglych(wydzial, rok)
    assert l.count() == 1


def test_serializuj_pbn_ciagle(wydawnictwo_ciagle_z_autorem, wydzial):
    wydawnictwo_ciagle_z_autorem.serializuj_dla_pbn(wydzial)


def test_serializuj_pbn_zwarte(wydawnictwo_zwarte_z_autorem, wydzial):
    wydawnictwo_zwarte_z_autorem.serializuj_dla_pbn(wydzial)


def test_eksport_pbn(normal_django_user, jednostka, autor_jan_kowalski, wydawnictwo_ciagle, wydawnictwo_zwarte):
    autor_jan_kowalski.dodaj_jednostke(jednostka=jednostka)

    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    wydawnictwo_zwarte.dodaj_autora(autor_jan_kowalski, jednostka)

    eksport_pbn(normal_django_user.pk, jednostka.wydzial.pk, datetime.now().date().year)

    assert PlikEksportuPBN.objects.all().count() == 1
