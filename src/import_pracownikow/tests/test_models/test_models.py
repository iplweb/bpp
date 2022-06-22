import pytest

from import_pracownikow.tests.conftest import (
    import_pracownikow_factory,
    testdata_xls_path_factory,
)

from bpp.models import Autor, Autor_Jednostka


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


def test_ImportPracownikow_brak_naglowka(import_pracownikow_brak_naglowka):
    import_pracownikow_brak_naglowka.perform()
    assert import_pracownikow_brak_naglowka.importpracownikowrow_set.count() == 0
