"""Opcja „Nadpisuj daty zatrudnienia (od/do) wartościami z pliku" —
flaga modelu, bramka zmian, nadpisywanie w integracji, pre-check
nakładania okresów, licznik ostrzeżenia finalizacji (spec
2026-07-26-import-nadpisywanie-dat-zatrudnienia-design.md)."""

from datetime import date

import pytest
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.forms import NowyImportForm
from import_pracownikow.models import ImportPracownikow, ImportPracownikowRow


@pytest.mark.django_db
def test_flaga_nadpisywania_domyslnie_wylaczona():
    parent = baker.make(ImportPracownikow)
    assert parent.nadpisuj_daty_zatrudnienia is False


def test_formularz_ma_pole_nadpisywania_dat():
    form = NowyImportForm()
    assert "nadpisuj_daty_zatrudnienia" in form.fields
    assert form.fields["nadpisuj_daty_zatrudnienia"].initial in (None, False)


@pytest.mark.django_db
def test_formularz_pole_nadpisywania_w_szufladzie():
    from crispy_forms.utils import render_crispy_form

    html = render_crispy_form(NowyImportForm())
    assert "<details" in html
    pozycja_details = html.index("<details")
    pozycja_pola = html.index("nadpisuj_daty_zatrudnienia")
    assert pozycja_pola > pozycja_details


def _row_z_data(parent, dane, autor, jednostka, aj):
    return baker.make(
        ImportPracownikowRow,
        parent=parent,
        autor=autor,
        jednostka=jednostka,
        autor_jednostka=aj,
        dane_znormalizowane=dane,
    )


def _scenariusz_tytulowy(nadpisuj):
    """Otwarty okres od 2026-07-19 (fallback z poprzedniego importu),
    plik niesie 2021-10-01. Jedyna różnica wiersza = data od."""
    parent = baker.make(ImportPracownikow, nadpisuj_daty_zatrudnienia=nadpisuj)
    autor, jednostka = baker.make(Autor), baker.make(Jednostka)
    aj = baker.make(
        Autor_Jednostka,
        autor=autor,
        jednostka=jednostka,
        rozpoczal_prace=date(2026, 7, 19),
        zakonczyl_prace=None,
        podstawowe_miejsce_pracy=True,
    )
    row = _row_z_data(parent, {"data_zatrudnienia": "2021-10-01"}, autor, jednostka, aj)
    return row, aj


@pytest.mark.django_db
def test_bramka_roznica_dat_flaga_on():
    row, _ = _scenariusz_tytulowy(nadpisuj=True)
    assert row.check_if_integration_needed() is True


@pytest.mark.django_db
def test_bramka_roznica_dat_flaga_off_jak_dzis():
    row, _ = _scenariusz_tytulowy(nadpisuj=False)
    assert row.check_if_integration_needed() is False
