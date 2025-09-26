#!/usr/bin/env python
"""
Test file validation for import_polon forms
Run with: python src/manage.py shell < src/import_polon/test_file_validation.py
"""
from django.core.files.uploadedfile import SimpleUploadedFile

from import_polon.forms import NowyImportAbsencjiForm, NowyImportForm


def test_polon_file_validation():
    print("Testing file validation in import_polon forms...")

    # Test 1: NowyImportForm with invalid file extension (.txt)
    print("\n1. Testing NowyImportForm with .txt file:")
    txt_file = SimpleUploadedFile(
        "test.txt", b"Not CSV or Excel", content_type="text/plain"
    )
    form_data = {
        "rok": 2023,
        "zapisz_zmiany_do_bazy": False,
        "ukryj_niezmatchowanych_autorow": True,
    }
    form = NowyImportForm(data=form_data, files={"plik": txt_file})

    if not form.is_valid():
        print("✓ Validation failed as expected")
        if "plik" in form.errors:
            print(f"  Error message: {form.errors['plik'][0]}")
    else:
        print("✗ Form should not be valid with .txt file")

    # Test 2: NowyImportForm with valid .csv extension
    print("\n2. Testing NowyImportForm with .csv file:")
    csv_file = SimpleUploadedFile("test.csv", b"CSV content", content_type="text/csv")
    form = NowyImportForm(data=form_data, files={"plik": csv_file})

    if form.is_valid():
        print("✓ Form validation passed for .csv file")
    else:
        print(f"✗ Form should be valid with .csv file: {form.errors}")

    # Test 3: NowyImportForm with valid .xlsx extension
    print("\n3. Testing NowyImportForm with .xlsx file:")
    xlsx_file = SimpleUploadedFile(
        "test.xlsx",
        b"Mock Excel",
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )
    form = NowyImportForm(data=form_data, files={"plik": xlsx_file})

    if form.is_valid():
        print("✓ Form validation passed for .xlsx file")
    else:
        print(f"✗ Form should be valid with .xlsx file: {form.errors}")

    # Test 4: NowyImportAbsencjiForm with invalid file (.pdf)
    print("\n4. Testing NowyImportAbsencjiForm with .pdf file:")
    pdf_file = SimpleUploadedFile("test.pdf", b"PDF", content_type="application/pdf")
    absencji_form_data = {"zapisz_zmiany_do_bazy": False}
    form = NowyImportAbsencjiForm(data=absencji_form_data, files={"plik": pdf_file})

    if not form.is_valid():
        print("✓ Validation failed as expected")
        if "plik" in form.errors:
            print(f"  Error message: {form.errors['plik'][0]}")
    else:
        print("✗ Form should not be valid with .pdf file")

    # Test 5: NowyImportAbsencjiForm with valid .xls extension
    print("\n5. Testing NowyImportAbsencjiForm with .xls file:")
    xls_file = SimpleUploadedFile(
        "test.xls", b"XLS", content_type="application/vnd.ms-excel"
    )
    form = NowyImportAbsencjiForm(data=absencji_form_data, files={"plik": xls_file})

    if form.is_valid():
        print("✓ Form validation passed for .xls file")
    else:
        print(f"✗ Form should be valid with .xls file: {form.errors}")

    print("\n✓ All import_polon file validation tests completed!")


# Run the test
test_polon_file_validation()
