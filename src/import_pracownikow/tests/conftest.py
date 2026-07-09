import os

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from model_bakery import baker

from bpp.models import Autor, Autor_Jednostka, Jednostka
from import_pracownikow.models import ImportPracownikow


def xls_path_factory(suffix=""):
    return os.path.join(os.path.dirname(__file__), "", f"testdata{suffix}.xlsx")


def import_pracownikow_factory(user, path):
    i = ImportPracownikow(owner=user)
    with open(path, "rb") as f:
        i.plik_xls = SimpleUploadedFile(
            "import_dyscyplin_zrodel_przyklad.xlsx", f.read()
        )
    i.save()
    return i


@pytest.fixture
def testdata_xlsx_path():
    return xls_path_factory()


@pytest.fixture
def testdata_brak_naglowka_xlsx_path():
    return xls_path_factory("_brak_naglowka")


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


@pytest.fixture
def dwa_autory_z_jednostka():
    """(Autor, Jednostka) matchowalne przez ``matchuj_autora``/``matchuj_jednostke``.

    Nazwa fixture nawiązuje do docelowego scenariusza analizy dwóch wierszy
    pliku (jeden autor już powiązany z jednostką) — na Task 3 wystarczy
    pojedyncza para, na której testy dry-run weryfikują brak zapisu do
    domeny. ``Autor_Jednostka`` i ``aktualna_jednostka`` są ustawione z
    góry, tak jak w prawdziwych danych kadrowych (autor już zatrudniony).
    """
    jednostka = baker.make(
        Jednostka,
        nazwa="Katedra Testowa",
        skrot="Kat. Test.",
    )
    autor = baker.make(
        Autor, nazwisko="Kowalski", imiona="Jan", aktualna_jednostka=jednostka
    )
    baker.make(Autor_Jednostka, autor=autor, jednostka=jednostka)
    return autor, jednostka
