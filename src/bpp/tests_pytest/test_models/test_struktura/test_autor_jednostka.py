# -*- encoding: utf-8 -*-
from datetime import date, timedelta

import pytest
from django.db.utils import InternalError, IntegrityError
from model_mommy import mommy

from bpp.models.autor import Autor_Jednostka


@pytest.mark.django_db
def test_autor_jednostka_trigger_nie_mozna_zmienic_id_autora(autor_jan_kowalski, autor_jan_nowak, jednostka):
    aj = mommy.make(Autor_Jednostka, autor=autor_jan_kowalski, jednostka=jednostka)
    aj.autor = autor_jan_nowak
    with pytest.raises(InternalError):
        aj.save()


@pytest.mark.django_db
def test_autor_jednostka_trigger_nie_mozna_daty_w_przyszlosci(autor_jan_kowalski, jednostka):
    aj = mommy.make(Autor_Jednostka, autor=autor_jan_kowalski, jednostka=jednostka)
    aj.zakonczyl_prace = date.today()
    with pytest.raises(IntegrityError):
        aj.save()


@pytest.mark.django_db
def test_autor_jednostka_trigger_ustaw_aktualna_jednostke_1(autor_jan_kowalski, jednostka):
    aj = mommy.make(Autor_Jednostka, autor=autor_jan_kowalski, jednostka=jednostka)
    autor_jan_kowalski.refresh_from_db()
    assert autor_jan_kowalski.aktualny == True
    assert autor_jan_kowalski.aktualna_jednostka == jednostka

    aj.zakonczyl_prace = date.today() - timedelta(days=5)
    aj.save()
    autor_jan_kowalski.refresh_from_db()
    assert autor_jan_kowalski.aktualny == False
    assert autor_jan_kowalski.aktualna_jednostka == jednostka

    aj.delete()
    autor_jan_kowalski.refresh_from_db()
    assert autor_jan_kowalski.aktualny == False
    assert autor_jan_kowalski.aktualna_jednostka == None


@pytest.mark.django_db
def test_autor_jednostka_trigger_ustaw_aktualna_jednostke_2(autor_jan_kowalski, jednostka, druga_jednostka):
    aj1 = mommy.make(Autor_Jednostka, autor=autor_jan_kowalski, jednostka=jednostka,
                     rozpoczal_prace=date(2012, 1, 1),
                     zakonczyl_prace=date(2012, 2, 1))
    aj2 = mommy.make(Autor_Jednostka, autor=autor_jan_kowalski, jednostka=druga_jednostka,
                     rozpoczal_prace=date(2012, 1, 1),
                     zakonczyl_prace=date(2012, 2, 2))
    autor_jan_kowalski.refresh_from_db()

    assert autor_jan_kowalski.aktualna_jednostka == druga_jednostka
