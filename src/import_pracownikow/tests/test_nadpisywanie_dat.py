"""Opcja „Nadpisuj daty zatrudnienia (od/do) wartościami z pliku" —
flaga modelu, bramka zmian, nadpisywanie w integracji, pre-check
nakładania okresów, licznik ostrzeżenia finalizacji (spec
2026-07-26-import-nadpisywanie-dat-zatrudnienia-design.md)."""

import pytest
from model_bakery import baker

from import_pracownikow.forms import NowyImportForm
from import_pracownikow.models import ImportPracownikow


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
