"""Faza integracji: tworzenie NOWYCH okresów zatrudnienia (nowy Autor_Jednostka)
gdy plik niesie inną „datę od" niż baza + licznik (§8/§10 spec sync dat).
"""

from datetime import date

import pytest
from model_bakery import baker

from bpp.models import Autor_Jednostka
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.pipeline.integrate import _integruj_wiersz


def _row_odroczony_okres(imp, autor, jednostka, dane, rozpoczal_iso, *, nowy_okres):
    return ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=jednostka,
        autor_jednostka=None,
        dane_znormalizowane=dane,
        diff_do_utworzenia={
            "autor_jednostka": {
                "autor": autor.pk,
                "jednostka": jednostka.pk,
                "rozpoczal_prace": rozpoczal_iso,
                "nowy_okres": nowy_okres,
            }
        },
        zmiany_potrzebne=True,
    )


@pytest.mark.django_db
def test_nowy_okres_tworzy_drugi_aj_gdy_stary_zamkniety(autor_jednostka_fixture):
    """Inna data od przy ZAMKNIĘTYM starym okresie → NOWY Autor_Jednostka OBOK
    istniejącego (osoba odeszła i wraca). Stary okres nietknięty (P2 — nie
    domykamy; tu był już zamknięty)."""
    autor, jednostka = autor_jednostka_fixture
    stary = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2010, 1, 1),
        zakonczyl_prace=date(2015, 1, 1),
    )
    imp = baker.make(ImportPracownikow)
    row = _row_odroczony_okres(
        imp,
        autor,
        jednostka,
        {"data_zatrudnienia": "2022-09-01"},
        "2022-09-01",
        nowy_okres=True,
    )
    _integruj_wiersz(row)
    okresy = Autor_Jednostka.objects.filter(autor=autor, jednostka=jednostka)
    assert okresy.count() == 2
    stary.refresh_from_db()
    assert stary.zakonczyl_prace == date(2015, 1, 1)
    assert okresy.filter(rozpoczal_prace=date(2022, 9, 1)).exists()


@pytest.mark.django_db
def test_integruj_wiersz_zwraca_true_dla_nowego_okresu(autor_jednostka_fixture):
    """Zwrot ``_integruj_wiersz`` = przewód licznika ``utworzono_nowych_okresow``
    (N1): utworzono AJ oznaczony nowy_okres → True."""
    autor, jednostka = autor_jednostka_fixture
    baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2010, 1, 1),
        zakonczyl_prace=date(2015, 1, 1),
    )
    imp = baker.make(ImportPracownikow)
    row = _row_odroczony_okres(
        imp,
        autor,
        jednostka,
        {"data_zatrudnienia": "2022-09-01"},
        "2022-09-01",
        nowy_okres=True,
    )
    assert _integruj_wiersz(row) is True


@pytest.mark.django_db
def test_pierwsze_powiazanie_nie_liczy_sie_jako_nowy_okres(autor_jednostka_fixture):
    """Pierwsze powiązanie (brak istniejącego AJ) → nowy_okres=False, więc NIE
    inkrementuje licznika, mimo że AJ powstał."""
    autor, jednostka = autor_jednostka_fixture
    imp = baker.make(ImportPracownikow)
    row = _row_odroczony_okres(
        imp,
        autor,
        jednostka,
        {"data_zatrudnienia": "2022-09-01"},
        "2022-09-01",
        nowy_okres=False,
    )
    assert _integruj_wiersz(row) is False
    assert Autor_Jednostka.objects.filter(autor=autor, jednostka=jednostka).count() == 1


@pytest.mark.django_db
def test_okres_przylegajacy_scalony_nie_liczy_sie_jako_nowy(autor_jednostka_fixture):
    """Audyt #3: nowy okres, którego „data od" = koniec zamkniętego + 1 dzień,
    zostaje scalony przez defragmentację w JEDEN ciągły okres. Wtedy netto nie
    powstał nowy okres — ``_integruj_wiersz`` NIE może zwrócić True (inaczej
    panel raportuje „utworzono 1 okres" dla okresu, którego już nie ma)."""
    autor, jednostka = autor_jednostka_fixture
    baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2010, 1, 1),
        zakonczyl_prace=date(2015, 1, 1),
    )
    imp = baker.make(ImportPracownikow)
    row = _row_odroczony_okres(
        imp,
        autor,
        jednostka,
        {"data_zatrudnienia": "2015-01-02"},  # dzień po końcu → sąsiedztwo
        "2015-01-02",
        nowy_okres=True,
    )
    wynik = _integruj_wiersz(row)
    okresy = Autor_Jednostka.objects.filter(autor=autor, jednostka=jednostka)
    assert okresy.count() == 1  # scalone w jeden ciągły okres
    assert wynik is False  # nie liczymy scalonego okresu jako utworzonego


@pytest.mark.django_db
def test_idempotencja_drugi_przebieg_nie_tworzy_trzeciego_okresu(
    autor_jednostka_fixture,
):
    """Restart integracji (guard ``log_zmian``) → drugi ``_integruj_wiersz`` nie
    tworzy kolejnego AJ i zwraca False (nie liczy okresu ponownie)."""
    autor, jednostka = autor_jednostka_fixture
    baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2010, 1, 1),
        zakonczyl_prace=date(2015, 1, 1),
    )
    imp = baker.make(ImportPracownikow)
    row = _row_odroczony_okres(
        imp,
        autor,
        jednostka,
        {"data_zatrudnienia": "2022-09-01"},
        "2022-09-01",
        nowy_okres=True,
    )
    assert _integruj_wiersz(row) is True
    row.refresh_from_db()
    assert _integruj_wiersz(row) is False
    assert Autor_Jednostka.objects.filter(autor=autor, jednostka=jednostka).count() == 2
