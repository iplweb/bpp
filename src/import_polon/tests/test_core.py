from pathlib import Path

import pytest
from model_bakery import baker

from import_polon.core import (
    analyze_excel_file_import_absencji,
    analyze_excel_file_import_polon,
)
from import_polon.models import ImportPlikuAbsencji, ImportPlikuPolon

from bpp.models import Autor


@pytest.fixture
def fn_test_import_polon():
    return Path(__file__).parent / "test_import_polon.xlsx"


@pytest.fixture
def fn_test_import_absencji():
    return Path(__file__).parent / "test_import_absencji.xlsx"


@pytest.mark.django_db
def test_analyze_excel_file_import_polon(fn_test_import_polon):
    ipp = baker.make(ImportPlikuPolon)
    analyze_excel_file_import_polon(fn_test_import_polon, ipp)


@pytest.mark.django_db
def test_analyze_excel_file_import_absencji(fn_test_import_absencji):
    ipa = baker.make(ImportPlikuAbsencji, zapisz_zmiany_do_bazy=True)

    jan_kowalski: Autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    jan_kowalski.autor_absencja_set.create(rok=2017, ile_dni=50)

    adam_nowak: Autor = baker.make(
        Autor, nazwisko="Nowak", imiona="Adam", orcid="0001-0009-3366-100X"
    )
    adam_nowak_2: Autor = baker.make(Autor, nazwisko="Nowak", imiona="Adam")

    analyze_excel_file_import_absencji(fn_test_import_absencji, ipa)

    assert jan_kowalski.autor_absencja_set.get(rok=2017).ile_dni == 141
    assert jan_kowalski.autor_absencja_set.get(rok=2018).ile_dni == 352

    assert adam_nowak.autor_absencja_set.get(rok=2020).ile_dni == 100
    assert adam_nowak_2.autor_absencja_set.count() == 0
