"""Regresja: pusta komórka OSWIADCZENIE_O_DYSCYPLINACH nie może wywracać importu.

pandas zamienia pustą komórkę na ``None`` (``replace({np.nan: None})``), a
``row.get(klucz, "")`` zwraca wtedy ``None`` — domyślna wartość działa tylko
dla BRAKUJĄCEGO klucza. Dawniej ``.lower()`` na ``None`` kończyło się
``AttributeError`` i przerwaniem całego importu.
"""

import pandas as pd
import pytest
from django.core.files import File
from liveops.testing import MockProgress
from model_bakery import baker

from import_polon.core.import_polon import (
    _process_disciplines_from_row,
    analyze_file_import_polon,
)
from import_polon.models import ImportPlikuPolon, WierszImportuPlikuPolon


@pytest.mark.parametrize("wartosc", [None, "", "  "])
def test_process_disciplines_puste_oswiadczenie_o_dyscyplinach(wartosc):
    row = {"OSWIADCZENIE_N": "Nie", "OSWIADCZENIE_O_DYSCYPLINACH": wartosc}
    assert _process_disciplines_from_row(row) == (None, None, False)


def test_process_disciplines_oswiadczenie_tak_ze_spacjami():
    row = {
        "OSWIADCZENIE_N": None,
        "OSWIADCZENIE_O_DYSCYPLINACH": " Tak ",
        "OSWIADCZONA_DYSCYPLINA_PIERWSZA": "filozofia",
        "OSWIADCZONA_DYSCYPLINA_DRUGA": None,
    }
    assert _process_disciplines_from_row(row) == ("filozofia", None, False)


@pytest.mark.django_db
def test_analyze_file_import_polon_pusta_komorka_oswiadczenia(tmp_path, uczelnia):
    df = pd.DataFrame(
        {
            "IMIE": ["Jan"],
            "NAZWISKO": ["Pusty-Oswiadczeniowy"],
            "ZATRUDNIENIE": [uczelnia.nazwa],
            "OSWIADCZENIE_N": [None],
            "OSWIADCZENIE_O_DYSCYPLINACH": [None],
        }
    )
    plik = tmp_path / "puste.xlsx"
    df.to_excel(plik, index=False)

    import_model = baker.make(
        ImportPlikuPolon,
        rok=2023,
        uczelnia=uczelnia,
        zapisz_zmiany_do_bazy=False,
        ukryj_niezmatchowanych_autorow=False,
        ignoruj_miejsce_pracy=False,
    )
    with open(plik, "rb") as f:
        import_model.plik.save("puste.xlsx", File(f))

    analyze_file_import_polon(str(plik), import_model, MockProgress(import_model))

    wiersz = WierszImportuPlikuPolon.objects.get(parent=import_model)
    assert wiersz.rezultat == "Nie udało się dopasować autora"
