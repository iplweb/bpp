import os

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from import_pracownikow.models import ImportPracownikow

from bpp.models import Autor, Jednostka


def testdata_xls_path_factory(suffix=""):
    return os.path.join(os.path.dirname(__file__), "", f"testdata{suffix}.xlsx")


def import_pracownikow_factory(user, path):
    i = ImportPracownikow(owner=user)
    i.plik_xls = SimpleUploadedFile(
        "import_dyscyplin_zrodel_przyklad.xlsx", open(path, "rb").read()
    )
    i.save()
    return i


@pytest.fixture
def testdata_xlsx_path():
    return testdata_xls_path_factory()


@pytest.fixture
def testdata_brak_naglowka_xlsx_path():
    return testdata_xls_path_factory("_brak_naglowka")


@pytest.fixture
def autor_z_pliku():
    return baker.make(Autor, nazwisko="Kowalski", imiona="Jan", pk=50)


@pytest.fixture
def jednostka_z_pliku():
    return baker.make(
        Jednostka,
        nazwa="Katedra i Klinika Dermatologii, Wenerologii i Dermatologii Dziecięcej",
        skrot="Kat. i Klin. Derm., Wen. i Derm. Dz.",
    )


@pytest.fixture
def baza_importu_pracownikow(autor_z_pliku, jednostka_z_pliku):
    pass


@pytest.fixture
def autor_spoza_pliku():
    return baker.make(Autor, nazwisko="Nowak", imiona="Marian", pk=100)


@pytest.fixture
def jednostka_spoza_pliku() -> Jednostka:
    return baker.make(
        Jednostka,
        nazwa="Jednostka Spozaplikowa",
        skrot="Jedn. Spoz.",
        zarzadzaj_automatycznie=True,
    )


@pytest.fixture
def import_pracownikow(admin_user, baza_importu_pracownikow, testdata_xlsx_path):
    return import_pracownikow_factory(admin_user, testdata_xlsx_path)


@pytest.fixture
def import_pracownikow_performed(import_pracownikow) -> ImportPracownikow:
    import_pracownikow.perform()
    return import_pracownikow


@pytest.fixture
def import_pracownikow_brak_naglowka(admin_user, testdata_brak_naglowka_xlsx_path):
    return import_pracownikow_factory(admin_user, testdata_brak_naglowka_xlsx_path)
