"""Resolver okresu zatrudnienia po „dacie od" (§7 spec
``2026-07-13-import-pracownikow-synchronizacja-dat-zatrudnienia``).

Po jednym teście na wiersz tabeli decyzyjnej §3 + parytet sortowania NULL-dat
(N2), kontrakt typu ``date`` (N5) i brak zapytania przy ``aj_lista=`` (N+1).
"""

from datetime import date

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.okresy import (
    _wybierz_aktywny_najswiezszy,
    rozwiaz_okres_zatrudnienia,
)


@pytest.fixture
def para():
    return baker.make(Autor), baker.make(Jednostka)


@pytest.mark.django_db
def test_brak_aj_data_w_pliku_tworzy_nowy(para):
    autor, jednostka = para
    assert rozwiaz_okres_zatrudnienia(autor, jednostka, date(2020, 1, 1)) == (
        "nowy",
        date(2020, 1, 1),
    )


@pytest.mark.django_db
def test_brak_aj_pusty_plik_tworzy_nowy_none(para):
    autor, jednostka = para
    assert rozwiaz_okres_zatrudnienia(autor, jednostka, None) == ("nowy", None)


@pytest.mark.django_db
def test_ta_sama_data_od_zwraca_istniejacy(para):
    autor, jednostka = para
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2020, 1, 1),
    )
    assert rozwiaz_okres_zatrudnienia(autor, jednostka, date(2020, 1, 1)) == (
        "istniejacy",
        aj,
    )


@pytest.mark.django_db
def test_wypelnienie_null_zwraca_istniejacy(para):
    autor, jednostka = para
    aj = baker.make(
        Autor_Jednostka, autor=autor, jednostka=jednostka, rozpoczal_prace=None
    )
    assert rozwiaz_okres_zatrudnienia(autor, jednostka, date(2021, 5, 5)) == (
        "istniejacy",
        aj,
    )


@pytest.mark.django_db
def test_inna_data_od_przy_zamknietym_okresie_tworzy_nowy(para):
    # Wszystkie istniejące okresy ZAMKNIĘTE → nowy okres (osoba odeszła i wraca).
    autor, jednostka = para
    baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2010, 1, 1),
        zakonczyl_prace=date(2015, 1, 1),
    )
    assert rozwiaz_okres_zatrudnienia(autor, jednostka, date(2022, 9, 1)) == (
        "nowy",
        date(2022, 9, 1),
    )


@pytest.mark.django_db
def test_inna_data_od_przy_otwartym_okresie_celuje_w_aktywny(para):
    # Otwarty (trwający) okres → inna data od NIE tworzy nowego (defragmentuj by
    # go scalił); celujemy w aktywny, różnicę pokaże podgląd (decyzja usera A).
    autor, jednostka = para
    aktywny = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2010, 1, 1),
        zakonczyl_prace=None,
    )
    assert rozwiaz_okres_zatrudnienia(autor, jednostka, date(2022, 9, 1)) == (
        "istniejacy",
        aktywny,
    )


@pytest.mark.django_db
def test_istniejacy_pusty_plik_zwraca_aktywny_najswiezszy(para):
    autor, jednostka = para
    baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2010, 1, 1),
        zakonczyl_prace=date(2015, 1, 1),
    )
    aktywny = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2016, 1, 1),
        zakonczyl_prace=None,
    )
    assert rozwiaz_okres_zatrudnienia(autor, jednostka, None) == ("istniejacy", aktywny)


@pytest.mark.django_db
def test_wiele_null_rozpoczal_deterministyczny_po_pk(para):
    autor, jednostka = para
    a1 = baker.make(
        Autor_Jednostka, autor=autor, jednostka=jednostka, rozpoczal_prace=None
    )
    a2 = baker.make(
        Autor_Jednostka, autor=autor, jednostka=jednostka, rozpoczal_prace=None
    )
    _, wybrany = rozwiaz_okres_zatrudnienia(autor, jednostka, date(2020, 1, 1))
    assert wybrany == min(a1, a2, key=lambda aj: aj.pk)


class _AJ:
    """Lekki obiekt AJ dla czystej funkcji (bez ORM)."""

    def __init__(self, pk, rozpoczal, zakonczyl=None):
        self.pk = pk
        self.rozpoczal_prace = rozpoczal
        self.zakonczyl_prace = zakonczyl


def test_wybierz_aktywny_najswiezszy_null_jak_najswiezszy_bez_typeerror():
    # Parytet z SQL NULLS FIRST (DESC): rozpoczal=None traktowany jako
    # „najświeższy"; brak TypeError na porównaniu date z None.
    datowany = _AJ(1, date(2020, 1, 1))
    nullowy = _AJ(2, None)
    assert _wybierz_aktywny_najswiezszy([datowany, nullowy]) is nullowy
    assert _wybierz_aktywny_najswiezszy([nullowy, datowany]) is nullowy


def test_wybierz_aktywny_preferuje_aktywny_etat():
    historyczny = _AJ(1, date(2020, 1, 1), zakonczyl=date(2021, 1, 1))
    aktywny = _AJ(2, date(2015, 1, 1), zakonczyl=None)
    assert _wybierz_aktywny_najswiezszy([historyczny, aktywny]) is aktywny


def test_wybierz_aktywny_pusta_lista_none():
    assert _wybierz_aktywny_najswiezszy([]) is None


@pytest.mark.django_db
def test_aj_lista_przekazana_nie_odpala_zapytania(para):
    autor, jednostka = para
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2020, 1, 1),
    )
    with CaptureQueriesContext(connection) as ctx:
        rozwiaz_okres_zatrudnienia(autor, jednostka, date(2020, 1, 1), aj_lista=[aj])
    assert len(ctx.captured_queries) == 0


@pytest.mark.django_db
def test_date_na_wejsciu_trafia_w_istniejacy_okres(para):
    # N5: kontrakt — plik_od jako `date` poprawnie dopasowuje istniejący okres
    # (ISO-string dałby zawsze „nowy" + duplikat AJ).
    autor, jednostka = para
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2020, 1, 1),
    )
    rodzaj, wartosc = rozwiaz_okres_zatrudnienia(
        autor, jednostka, date(2020, 1, 1), aj_lista=[aj]
    )
    assert rodzaj == "istniejacy"
    assert wartosc is aj
