from unittest.mock import patch

import pytest
from liveops.testing import MockProgress
from model_bakery import baker

from import_pracownikow.models import ImportPracownikow
from import_pracownikow.pipeline.analyze import analizuj


def _imp():
    imp = baker.make(ImportPracownikow, stan=ImportPracownikow.STAN_ZMAPOWANY)
    imp.plik_xls.name = "protected/import_pracownikow/x.csv"
    return imp


def _analizuj_z_wierszem(imp, wiersz):
    with patch("import_pracownikow.pipeline.analyze.otworz_zrodlo") as MZ:
        MZ.return_value.count.return_value = 1
        MZ.return_value.data.return_value = iter([wiersz])
        analizuj(imp, MockProgress(imp))  # NIE rzuca


@pytest.mark.django_db
def test_niepoprawny_email_nie_wywala_analizy_i_ostrzega(uczelnia):
    imp = _imp()
    _analizuj_z_wierszem(
        imp,
        {
            "imię": "Jan",
            "nazwisko": "Kowalski",
            "nazwa_jednostki": "Zakład Testowy",
            "email": "nie-email",
            "__xls_loc_sheet__": 0,
            "__xls_loc_row__": 1,
        },
    )
    row = imp.importpracownikowrow_set.get()
    assert row.dane_znormalizowane.get("email") == ""
    ostrzezenia = row.dane_znormalizowane.get("ostrzeżenia") or []
    assert any("e-mail" in o.lower() for o in ostrzezenia)


@pytest.mark.django_db
def test_poprawny_email_normalizowany_bez_ostrzezenia(uczelnia):
    imp = _imp()
    _analizuj_z_wierszem(
        imp,
        {
            "imię": "Anna",
            "nazwisko": "Nowak",
            "nazwa_jednostki": "Zakład Testowy",
            "email": "  Anna.Nowak@EXAMPLE.com ",
            "__xls_loc_sheet__": 0,
            "__xls_loc_row__": 2,
        },
    )
    row = imp.importpracownikowrow_set.get()
    assert row.dane_znormalizowane.get("email") == "anna.nowak@example.com"
    assert "ostrzeżenia" not in row.dane_znormalizowane
