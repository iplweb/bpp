import os

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from model_mommy import mommy

from import_pracownikow.models import ImportPracownikow

from bpp.models import Autor, Autor_Jednostka, Jednostka


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
def baza_importu_pracownikow():
    mommy.make(
        Jednostka,
        nazwa="Katedra i Klinika Dermatologii, Wenerologii i Dermatologii Dziecięcej",
    )
    mommy.make(Autor, nazwisko="Kowalski", imiona="Jan", pk=50)


@pytest.fixture
def import_pracownikow(admin_user, baza_importu_pracownikow, testdata_xlsx_path):
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


def test_ImportPracownikow_perform_aktualizacja_tytulu_nastapila(
    import_pracownikow, tytuly
):
    import_pracownikow.perform()
    assert Autor.objects.get(pk=50).tytul.skrot == "lek. med."


@pytest.mark.django_db
def test_ImportPracownikow_perform_aktualizacja_tytulu_brakujacy_tytul(
    baza_importu_pracownikow, admin_user
):
    ip = import_pracownikow_factory(
        admin_user, testdata_xls_path_factory("_nieistn_tytul")
    )

    ip.perform()
    assert Autor.objects.get(pk=50).tytul is None


@pytest.fixture
def import_pracownikow_brak_naglowka(admin_user, testdata_brak_naglowka_xlsx_path):
    return import_pracownikow_factory(admin_user, testdata_brak_naglowka_xlsx_path)


def test_ImportPracownikow_brak_naglowka(import_pracownikow_brak_naglowka):
    import_pracownikow_brak_naglowka.perform()
    assert import_pracownikow_brak_naglowka.importpracownikowrow_set.count() == 0
