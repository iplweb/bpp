import pytest

from import_common.exceptions import BadNoOfSheetsException, ImproperFileException
from import_dyscyplin.core import przeanalizuj_plik_xls
from import_dyscyplin.models import Import_Dyscyplin_Row


def test_przeanalizuj_plik_xls_zly_plik(conftest_py):
    with pytest.raises(ImproperFileException):
        przeanalizuj_plik_xls(conftest_py, parent=None)


def test_przeanalizuj_plik_xls_wiele_skoroszytow(test3_multiple_sheets_xlsx):
    with pytest.raises(BadNoOfSheetsException):
        przeanalizuj_plik_xls(test3_multiple_sheets_xlsx, parent=None)


def test_przeanalizuj_plik_xls_dobry(test1_xlsx, import_dyscyplin):
    import_dyscyplin.plik.save("test.xlsx", open(test1_xlsx, "rb"))
    import_dyscyplin.stworz_kolumny()

    przeanalizuj_plik_xls(test1_xlsx, parent=import_dyscyplin)
    assert Import_Dyscyplin_Row.objects.count() == 6
