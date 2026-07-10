"""#508 F6: deterministyczny wybór Autor_Jednostka przy multi-etacie."""

from datetime import date

import pytest
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.pipeline.analyze import _wybierz_autor_jednostka


@pytest.mark.django_db
def test_wybiera_aktywny_etat_nie_historyczny():
    # Autor z DWOMA AJ w TEJ SAMEJ jednostce: historyczny (zamknięty) i aktywny.
    # `.first()` bez porządku wybierał losowo — a ten AJ commit aktualizuje, więc
    # trafienie w historyczny nadpisywało zamknięte zatrudnienie. Musi wybrać
    # AKTYWNY.
    autor = baker.make(Autor)
    jednostka = baker.make(Jednostka)
    historyczny = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2010, 1, 1),
        zakonczyl_prace=date(2015, 12, 31),
    )
    aktywny = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2020, 1, 1),
        zakonczyl_prace=None,
    )
    wybrany = _wybierz_autor_jednostka(autor, jednostka)
    assert wybrany == aktywny
    assert wybrany != historyczny


@pytest.mark.django_db
def test_bez_aktywnego_wybiera_najnowszy_startem():
    autor = baker.make(Autor)
    jednostka = baker.make(Jednostka)
    baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2005, 1, 1),
        zakonczyl_prace=date(2008, 1, 1),
    )
    nowszy = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2012, 1, 1),
        zakonczyl_prace=date(2015, 1, 1),
    )
    assert _wybierz_autor_jednostka(autor, jednostka) == nowszy


@pytest.mark.django_db
def test_brak_aj_zwraca_none():
    autor = baker.make(Autor)
    jednostka = baker.make(Jednostka)
    assert _wybierz_autor_jednostka(autor, jednostka) is None
