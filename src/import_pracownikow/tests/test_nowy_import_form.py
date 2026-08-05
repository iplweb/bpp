"""Item 8+9: NowyImportForm wystawia i zapisuje pola „data zmian personalnych"
oraz „przepnij wszystkie prace na nowe jednostki"."""

from datetime import date

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from import_pracownikow.forms import NowyImportForm


def test_nowy_import_form_ma_pola_daty_i_przepniecia():
    assert "data_zmian_personalnych" in NowyImportForm.base_fields
    assert "przepnij_wszystkie_prace" in NowyImportForm.base_fields


@pytest.mark.django_db
def test_nowy_import_form_zapisuje_pola():
    plik = SimpleUploadedFile("p.csv", b"Osoba;Nazwa jednostki\n")
    form = NowyImportForm(
        data={
            "data_zmian_personalnych": "2024-09-01",
            "przepnij_wszystkie_prace": "on",
        },
        files={"plik_xls": plik},
    )
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    assert obj.data_zmian_personalnych == date(2024, 9, 1)
    assert obj.przepnij_wszystkie_prace is True


@pytest.mark.django_db
def test_nowy_import_form_pola_opcjonalne():
    """Data i przepięcie są opcjonalne — sam plik wystarcza (domyślnie:
    brak daty, przepięcie odznaczone)."""
    plik = SimpleUploadedFile("p.csv", b"Osoba;Nazwa jednostki\n")
    form = NowyImportForm(data={}, files={"plik_xls": plik})
    assert form.is_valid(), form.errors
    obj = form.save(commit=False)
    assert obj.data_zmian_personalnych is None
    assert obj.przepnij_wszystkie_prace is False
