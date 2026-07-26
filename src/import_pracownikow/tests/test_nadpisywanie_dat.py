"""Opcja „Nadpisuj daty zatrudnienia (od/do) wartościami z pliku" —
flaga modelu, bramka zmian, nadpisywanie w integracji, pre-check
nakładania okresów, licznik ostrzeżenia finalizacji (spec
2026-07-26-import-nadpisywanie-dat-zatrudnienia-design.md)."""

import pytest
from model_bakery import baker

from import_pracownikow.models import ImportPracownikow


@pytest.mark.django_db
def test_flaga_nadpisywania_domyslnie_wylaczona():
    parent = baker.make(ImportPracownikow)
    assert parent.nadpisuj_daty_zatrudnienia is False
