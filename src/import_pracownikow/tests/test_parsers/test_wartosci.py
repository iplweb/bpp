from datetime import date, datetime

import pytest

from import_pracownikow.parsers.wartosci import (
    normalize_date_pl,
    normalizuj_wartosci_wiersza,
)


@pytest.mark.parametrize(
    "wejscie,oczekiwane",
    [
        ("01.10.2016", date(2016, 10, 1)),  # polski DD.MM.YYYY
        ("2016-10-01", "2016-10-01"),  # ISO — zostaw dla ExcelDateField
        (datetime(2016, 10, 1, 12, 0), date(2016, 10, 1)),  # XLSX datetime
        (date(2016, 10, 1), date(2016, 10, 1)),  # date bez zmian
        ("", ""),  # puste — bez zmian
        ("cokolwiek", "cokolwiek"),  # nie-data — bez zmian (form odrzuci)
        (None, None),
    ],
)
def test_normalize_date_pl(wejscie, oczekiwane):
    assert normalize_date_pl(wejscie) == oczekiwane


def test_normalizuj_wartosci_wiersza_tylko_daty():
    elem = {
        "nazwisko": "Kowalski",
        "data_zatrudnienia": "01.10.2016",
        "data_końca_zatrudnienia": "",
        "wymiar_etatu": "1,0",
    }
    out = normalizuj_wartosci_wiersza(elem)
    assert out["data_zatrudnienia"] == date(2016, 10, 1)
    assert out["data_końca_zatrudnienia"] == ""  # puste bez zmian
    assert out["nazwisko"] == "Kowalski"  # nietknięte
    assert out["wymiar_etatu"] == "1,0"  # nie-data nietknięta
    # nie mutuje wejścia
    assert elem["data_zatrudnienia"] == "01.10.2016"
