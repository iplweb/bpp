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
from import_pracownikow.pipeline.integrate import _materializuj_diff, integruj


def _row_swiezy_okres(imp, autor, jednostka, dane, *, rozpoczal_prace=None):
    """Wiersz z odroczonym NOWYM okresem (diff_do_utworzenia['autor_jednostka'])
    do bezpośredniej materializacji — bez istniejącego AJ."""
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
                "rozpoczal_prace": rozpoczal_prace,
                "nowy_okres": False,
            }
        },
        zmiany_potrzebne=True,
    )


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
def test_swiezy_aj_bez_daty_w_pliku_uzywa_data_zmian(autor_jednostka_fixture):
    """P1: NOWY okres (świeży AJ z diff) i brak daty w pliku → globalna „data
    zmian personalnych" jako rozpoczal, stemplowana przy MATERIALIZACJI."""
    autor, jednostka = autor_jednostka_fixture
    imp = baker.make(ImportPracownikow, data_zmian_personalnych=date(2024, 9, 1))
    row = _row_swiezy_okres(imp, autor, jednostka, {})
    created = _materializuj_diff(row)
    assert created is True
    assert row.autor_jednostka.rozpoczal_prace == date(2024, 9, 1)


@pytest.mark.django_db
def test_istniejacy_aj_pusta_data_od_bez_zmian(autor_jednostka_fixture):
    """§5: istniejący AJ + pusty plik_od → NIC NIE ZMIENIAJ. rozpoczal zostaje
    NULL — NIE stemplujemy data_zmian/dziś na istniejącym AJ (fallback dotyczy
    tylko świeżego AJ przy materializacji)."""
    autor, jednostka = autor_jednostka_fixture
    aj = baker.make(
        Autor_Jednostka, autor=autor, jednostka=jednostka, rozpoczal_prace=None
    )
    imp = baker.make(ImportPracownikow, data_zmian_personalnych=date(2024, 9, 1))
    row = _row_z_aj(imp, autor, jednostka, aj, {})
    row._integrate_autor_jednostka()
    aj.refresh_from_db()
    assert aj.rozpoczal_prace is None


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
def test_swiezy_aj_bez_globalnej_daty_stempluje_dzis(autor_jednostka_fixture):
    """P1 fallback: świeży AJ (nowy okres), brak daty w pliku i brak globalnej
    „daty zmian" (None) → dzień importu (dziś). Priorytet: plik → globalna → dziś,
    stemplowany przy materializacji nowego AJ."""
    autor, jednostka = autor_jednostka_fixture
    imp = baker.make(ImportPracownikow, data_zmian_personalnych=None)
    row = _row_swiezy_okres(imp, autor, jednostka, {})
    _materializuj_diff(row)
    assert row.autor_jednostka.rozpoczal_prace == timezone.localdate()


@pytest.mark.django_db
def test_data_do_wstaw_gdy_pusta(autor_jednostka_fixture):
    """§3: „data do" z pliku wstawiana, gdy AJ nie ma jeszcze końca zatrudnienia."""
    autor, jednostka = autor_jednostka_fixture
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2010, 1, 1),
        zakonczyl_prace=None,
    )
    imp = baker.make(ImportPracownikow)
    row = _row_z_aj(
        imp, autor, jednostka, aj, {"data_końca_zatrudnienia": "2023-06-30"}
    )
    row._integrate_autor_jednostka()
    aj.refresh_from_db()
    assert aj.zakonczyl_prace == date(2023, 6, 30)


@pytest.mark.django_db
def test_data_do_nie_nadpisuje_istniejacej(autor_jednostka_fixture):
    """§3: „data do" z pliku NIE nadpisuje istniejącej daty końca (różnicę
    pokazuje tylko porównywarka, wstaw-tylko-gdy-pusta)."""
    autor, jednostka = autor_jednostka_fixture
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2010, 1, 1),
        zakonczyl_prace=date(2020, 12, 31),
    )
    imp = baker.make(ImportPracownikow)
    row = _row_z_aj(
        imp, autor, jednostka, aj, {"data_końca_zatrudnienia": "2023-06-30"}
    )
    row._integrate_autor_jednostka()
    aj.refresh_from_db()
    assert aj.zakonczyl_prace == date(2020, 12, 31)


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
