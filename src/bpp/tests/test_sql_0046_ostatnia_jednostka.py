# -*- encoding: utf-8 -*-

import pytest
from datetime import timedelta

from django.utils import timezone

from bpp.models.autor import Autor_Jednostka

@pytest.mark.django_db
def test_0046_ostatnia_jednostka_trigger_via_api(autor_jan_nowak, jednostka,
                                                 standard_data):
    jednostka.dodaj_autora(autor_jan_nowak)
    assert autor_jan_nowak.aktualna_jednostka == jednostka


@pytest.mark.django_db
def test_0046_ostatnia_jednostka_trigger(autor_jan_nowak, jednostka,
                                         druga_jednostka, standard_data):
    assert autor_jan_nowak.aktualna_jednostka == None

    two_months = timedelta(days=60)
    month = timedelta(days=30)

    # Strategia 3 test 1
    aj = Autor_Jednostka.objects.create(
        autor=autor_jan_nowak,
        jednostka=jednostka,
        rozpoczal_prace=timezone.now() - two_months,
        zakonczyl_prace=timezone.now() - month
    )
    autor_jan_nowak.refresh_from_db()
    assert autor_jan_nowak.aktualna_jednostka == jednostka

    aj.delete()
    autor_jan_nowak.refresh_from_db()
    assert autor_jan_nowak.aktualna_jednostka == None

    # Strategia 3 test 2
    aj = Autor_Jednostka.objects.create(
        autor=autor_jan_nowak,
        jednostka=jednostka,
    )
    autor_jan_nowak.refresh_from_db()
    assert autor_jan_nowak.aktualna_jednostka == jednostka

    aj.delete()
    autor_jan_nowak.refresh_from_db()
    assert autor_jan_nowak.aktualna_jednostka == None

    # Strategia 1
    aj = Autor_Jednostka.objects.create(
        autor=autor_jan_nowak,
        jednostka=jednostka,
        rozpoczal_prace=timezone.now() - two_months,
    )
    aj2 = Autor_Jednostka.objects.create(
        autor=autor_jan_nowak,
        jednostka=druga_jednostka,
        rozpoczal_prace=timezone.now() - two_months,
        zakonczyl_prace=timezone.now() - month
    )
    autor_jan_nowak.refresh_from_db()
    assert autor_jan_nowak.aktualna_jednostka == jednostka

    aj.delete()
    aj2.delete()
    autor_jan_nowak.refresh_from_db()
    assert autor_jan_nowak.aktualna_jednostka == None

    Autor_Jednostka.objects.all().delete()

    # Strategia 2
    aj = Autor_Jednostka.objects.create(
        autor=autor_jan_nowak,
        jednostka=jednostka,
        rozpoczal_prace=timezone.now() - two_months,
    )
    aj2 = Autor_Jednostka.objects.create(
        autor=autor_jan_nowak,
        jednostka=druga_jednostka,
        rozpoczal_prace=timezone.now() - month,
    )
    autor_jan_nowak.refresh_from_db()
    assert autor_jan_nowak.aktualna_jednostka == druga_jednostka

    aj.delete()
    aj2.delete()
    autor_jan_nowak.refresh_from_db()
    assert autor_jan_nowak.aktualna_jednostka == None


