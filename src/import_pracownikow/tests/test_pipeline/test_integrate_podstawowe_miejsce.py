"""Faza integracji: domyślne podstawowe miejsce pracy + stemplowanie daty (#4).

Decyzja usera: import ma ustawiać jednostkę autora (z wiersza) jako PODSTAWOWE
miejsce pracy, a pozostałe jednostki tego autora oznaczać jako NIE-podstawowe.
Datę rozpoczęcia pracy stemplujemy TYLKO gdy pusta — priorytet: data z pliku,
w razie braku data importu (dziś). Kolumna „Podstawowe miejsce pracy"=NIE w
pliku wyłącza to dla danego wiersza.
"""

from datetime import date

import pytest
from django.utils import timezone
from liveops.testing import MockProgress
from model_bakery import baker

from bpp.models import Autor_Jednostka, Jednostka
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow
from import_pracownikow.pipeline.integrate import integruj


def _row(imp, autor, jednostka, aj, **kwargs):
    dane = kwargs.pop("dane_znormalizowane", {})
    return ImportPracownikowRow.objects.create(
        parent=imp,
        autor=autor,
        jednostka=jednostka,
        autor_jednostka=aj,
        dane_znormalizowane=dane,
        diff_do_utworzenia={},
        zmiany_potrzebne=True,
        **kwargs,
    )


@pytest.mark.django_db
def test_import_ustawia_jednostke_jako_podstawowe_miejsce_pracy(
    autor_jednostka_fixture,
):
    """Domyślnie (bez kolumny w pliku) import ustawia jednostkę wiersza jako
    podstawowe miejsce pracy autora, a inną jednostkę tego autora → NIE."""
    autor, jednostka = autor_jednostka_fixture
    inna = baker.make(Jednostka)
    aj_inna = baker.make(
        Autor_Jednostka, autor=autor, jednostka=inna, podstawowe_miejsce_pracy=True
    )
    aj = baker.make(
        Autor_Jednostka, autor=autor, jednostka=jednostka, podstawowe_miejsce_pracy=None
    )
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)
    _row(imp, autor, jednostka, aj, podstawowe_miejsce_pracy=None)

    integruj(imp, MockProgress(imp))

    aj.refresh_from_db()
    aj_inna.refresh_from_db()
    assert aj.podstawowe_miejsce_pracy is True
    assert aj_inna.podstawowe_miejsce_pracy is False


@pytest.mark.django_db
def test_plik_nie_wylacza_podstawowego_miejsca(autor_jednostka_fixture):
    """Kolumna „Podstawowe miejsce pracy"=NIE (row.podstawowe_miejsce_pracy is
    False) zdejmuje flagę zamiast ustawiać."""
    autor, jednostka = autor_jednostka_fixture
    aj = baker.make(
        Autor_Jednostka, autor=autor, jednostka=jednostka, podstawowe_miejsce_pracy=True
    )
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)
    _row(imp, autor, jednostka, aj, podstawowe_miejsce_pracy=False)

    integruj(imp, MockProgress(imp))

    aj.refresh_from_db()
    assert aj.podstawowe_miejsce_pracy is False


@pytest.mark.django_db
def test_stempluje_date_importu_gdy_brak_w_pliku(autor_jednostka_fixture):
    """Brak daty w pliku + puste rozpoczal_prace → data importu (dziś)."""
    autor, jednostka = autor_jednostka_fixture
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=None,
        podstawowe_miejsce_pracy=None,
    )
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)
    _row(imp, autor, jednostka, aj, dane_znormalizowane={})

    integruj(imp, MockProgress(imp))

    aj.refresh_from_db()
    assert aj.rozpoczal_prace == timezone.localdate()


@pytest.mark.django_db
def test_stempluje_date_z_pliku_gdy_pusta(autor_jednostka_fixture):
    """Data zatrudnienia z pliku trafia do pustego rozpoczal_prace."""
    autor, jednostka = autor_jednostka_fixture
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=None,
        podstawowe_miejsce_pracy=None,
    )
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)
    _row(
        imp,
        autor,
        jednostka,
        aj,
        dane_znormalizowane={"data_zatrudnienia": "2025-03-01"},
    )

    integruj(imp, MockProgress(imp))

    aj.refresh_from_db()
    assert aj.rozpoczal_prace == date(2025, 3, 1)


@pytest.mark.django_db
def test_nie_nadpisuje_istniejacej_daty_rozpoczecia(autor_jednostka_fixture):
    """Istniejące rozpoczal_prace NIE jest nadpisywane — nawet gdy plik niesie
    inną datę (wiersz integrowany z powodu ustawiania podstawowego miejsca)."""
    autor, jednostka = autor_jednostka_fixture
    istnieje = date(2000, 1, 1)
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=istnieje,
        podstawowe_miejsce_pracy=None,
    )
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZATWIERDZONY)
    _row(
        imp,
        autor,
        jednostka,
        aj,
        dane_znormalizowane={"data_zatrudnienia": "2025-03-01"},
    )

    integruj(imp, MockProgress(imp))

    aj.refresh_from_db()
    assert aj.rozpoczal_prace == istnieje  # nie ruszone
    assert aj.podstawowe_miejsce_pracy is True  # ale primary jednak ustawione
