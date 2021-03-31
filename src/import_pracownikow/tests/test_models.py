import os

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from model_mommy import mommy

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.models import ImportPracownikow


def testdata_xls_path_factory(suffix=""):
    return os.path.join(os.path.dirname(__file__), f"testdata{suffix}.xlsx")


@pytest.fixture
def testdata_xlsx_path():
    return testdata_xls_path_factory()


@pytest.fixture
def testdata_brak_naglowka_xlsx_path():
    return testdata_xls_path_factory("_brak_naglowka")


def import_pracownikow_factory(user, path):
    i = ImportPracownikow(owner=user)
    i.plik_xls = SimpleUploadedFile(
        "import_dyscyplin_zrodel_przyklad.xlsx", open(path, "rb").read()
    )
    i.save()
    return i


@pytest.fixture
def import_pracownikow(admin_user, testdata_xlsx_path):
    mommy.make(
        Jednostka,
        nazwa="Katedra i Klinika Dermatologii, Wenerologii i Dermatologii Dziecięcej",
    )
    mommy.make(Autor, nazwisko="Kowalski", imiona="Jan", pk=50)

    return import_pracownikow_factory(admin_user, testdata_xlsx_path)


@pytest.fixture
def import_pracownikow_performed(import_pracownikow):
    import_pracownikow.perform()
    return import_pracownikow


def test_ImportPracownikow_perform(import_pracownikow):
    import_pracownikow.perform()
    assert import_pracownikow.importpracownikowrow_set.count() == 1
    assert import_pracownikow.importpracownikowrow_set.first().zmiany_potrzebne
    assert Autor_Jednostka.objects.count() == 1

    import_pracownikow.mark_reset()
    import_pracownikow.perform()
    assert not import_pracownikow.importpracownikowrow_set.first().zmiany_potrzebne


@pytest.fixture
def import_pracownikow_brak_naglowka(admin_user, testdata_brak_naglowka_xlsx_path):
    return import_pracownikow_factory(admin_user, testdata_brak_naglowka_xlsx_path)


def test_ImportPracownikow_brak_naglowka(import_pracownikow_brak_naglowka):
    import_pracownikow_brak_naglowka.perform()
    assert import_pracownikow_brak_naglowka.importpracownikowrow_set.count() == 0
