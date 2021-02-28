import os

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from import_pracownikow.exceptions import BłądDanychWejściowych
from import_pracownikow.models import ImportPracownikow


def testdata_xls_path_factory(suffix=""):
    return os.path.join(os.path.dirname(__name__), f"testdata{suffix}.xlsx")


@pytest.fixture
def testdata_xlsx_path():
    return testdata_xls_path_factory()


@pytest.fixture
def testdata_brak_naglowka_xlsx_path():
    return testdata_xls_path_factory("_brak_naglowka")


def import_pracownikow_factory(user, path):
    i = ImportPracownikow(owner=user)
    i.plik_xls = SimpleUploadedFile("testdata.xlsx", open(path, "rb").read())
    i.save()
    return i


@pytest.fixture
def import_pracownikow(admin_user, testdata_xlsx_path):
    return import_pracownikow_factory(admin_user, testdata_xlsx_path)


def test_ImportPracownikow_perform(import_pracownikow):
    import_pracownikow.perform()
    assert import_pracownikow.row_set.count() == 1


@pytest.fixture
def import_pracownikow_brak_naglowka(admin_user, testdata_brak_naglowka_xlsx_path):
    return import_pracownikow_factory(admin_user, testdata_brak_naglowka_xlsx_path)


def test_ImportPracownikow_brak_naglowka(import_pracownikow_brak_naglowka):
    with pytest.raises(BłądDanychWejściowych, match="Brak poprawnego wiersza"):
        import_pracownikow_brak_naglowka.perform()
