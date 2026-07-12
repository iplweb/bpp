"""Faza integracji: walidacja niezmienników dat zatrudnienia (uwaga reviewera #4).

``Autor_Jednostka.clean()`` waliduje relację ``rozpoczal_prace`` < ``zakonczyl_prace``,
ale ``Model.save()`` NIE woła ``clean()`` — a integracja zapisuje przez zwykłe
``aj.save()``. Bez guardu na ścieżce integracji odwrócony zakres z XLS trafia do
bazy. Guard MUSI odrzucić taki wiersz (``BPPDatabaseError``) zanim cokolwiek
zapisze.
"""

from datetime import date

import pytest
from django.utils import timezone
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor_Jednostka
from import_common.exceptions import BPPDatabaseError
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.pipeline.integrate import integruj


def _row_z_aj(imp, autor, jednostka, aj, dane):
    """Wiersz gotowy do bezpośredniego ``_integrate_autor_jednostka()`` —
    z zainicjowanym ``log_zmian`` (normalnie robi to ``integrate()``)."""
    row = ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=jednostka,
        autor_jednostka=aj,
        dane_znormalizowane=dane,
        diff_do_utworzenia={},
        zmiany_potrzebne=True,
    )
    row.log_zmian = {"autor": [], "autor_jednostka": []}
    return row


@pytest.mark.django_db
def test_data_zmian_wypelnia_nowe_aj_bez_daty_w_pliku(autor_jednostka_fixture):
    """Item 8: nowe powiązanie (rozpoczal_prace=None) i brak daty w pliku →
    globalna „data zmian personalnych" z importu jako data początku pracy."""
    autor, jednostka = autor_jednostka_fixture
    aj = baker.make(
        Autor_Jednostka, autor=autor, jednostka=jednostka, rozpoczal_prace=None
    )
    imp = baker.make(ImportPracownikow, data_zmian_personalnych=date(2024, 9, 1))
    row = _row_z_aj(imp, autor, jednostka, aj, {})
    row._integrate_autor_jednostka()
    aj.refresh_from_db()
    assert aj.rozpoczal_prace == date(2024, 9, 1)


@pytest.mark.django_db
def test_data_z_pliku_wygrywa_nad_globalna(autor_jednostka_fixture):
    """Item 8: data zatrudnienia z pliku ma pierwszeństwo przed globalną."""
    autor, jednostka = autor_jednostka_fixture
    aj = baker.make(
        Autor_Jednostka, autor=autor, jednostka=jednostka, rozpoczal_prace=None
    )
    imp = baker.make(ImportPracownikow, data_zmian_personalnych=date(2024, 9, 1))
    row = _row_z_aj(imp, autor, jednostka, aj, {"data_zatrudnienia": "2023-03-15"})
    row._integrate_autor_jednostka()
    aj.refresh_from_db()
    assert aj.rozpoczal_prace == date(2023, 3, 15)


@pytest.mark.django_db
def test_data_zmian_nie_nadpisuje_istniejacej_daty_aj(autor_jednostka_fixture):
    """Item 8: istniejąca data początku pracy NIE jest nadpisywana globalną
    (polityka „no-overwrite" — globalna tylko wypełnia brak)."""
    autor, jednostka = autor_jednostka_fixture
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2010, 1, 1),
    )
    imp = baker.make(ImportPracownikow, data_zmian_personalnych=date(2024, 9, 1))
    row = _row_z_aj(imp, autor, jednostka, aj, {})
    row._integrate_autor_jednostka()
    aj.refresh_from_db()
    assert aj.rozpoczal_prace == date(2010, 1, 1)


@pytest.mark.django_db
def test_brak_globalnej_daty_stempluje_date_importu(autor_jednostka_fixture):
    """Item 8 × #4: bez globalnej daty (None) i bez daty w pliku — nowe AJ
    dostaje datę importu (dziś). „data zmian personalnych" jest tylko środkowym
    ogniwem priorytetu (plik → globalna → dziś); ostatecznym fallbackiem pozostaje
    polityka #4 (puste rozpoczal_prace zawsze stemplujemy)."""
    autor, jednostka = autor_jednostka_fixture
    aj = baker.make(
        Autor_Jednostka, autor=autor, jednostka=jednostka, rozpoczal_prace=None
    )
    imp = baker.make(ImportPracownikow, data_zmian_personalnych=None)
    row = _row_z_aj(imp, autor, jednostka, aj, {})
    row._integrate_autor_jednostka()
    aj.refresh_from_db()
    assert aj.rozpoczal_prace == timezone.localdate()


@pytest.mark.django_db
def test_commit_odrzuca_odwrocony_zakres_dat(autor_jednostka_fixture):
    """Data rozpoczęcia >= data zakończenia → BPPDatabaseError, zero zapisu."""
    autor, jednostka = autor_jednostka_fixture
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=None,
        zakonczyl_prace=None,
    )
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)
    ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=jednostka,
        autor_jednostka=aj,
        dane_znormalizowane={
            "data_zatrudnienia": "2026-12-31",
            "data_końca_zatrudnienia": "2026-01-01",
        },
        diff_do_utworzenia={},
        zmiany_potrzebne=True,
    )

    with pytest.raises(BPPDatabaseError):
        integruj(imp, MockProgress(imp))

    aj.refresh_from_db()
    # Odwrócony zakres NIE został zapisany (transakcja per-wiersz wycofana).
    assert aj.rozpoczal_prace is None
    assert aj.zakonczyl_prace is None
