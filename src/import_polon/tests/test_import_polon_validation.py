"""
Tests for POLON import validation - ZATRUDNIENIE field and headers validation.
"""

import pandas as pd
import pytest
from django.core.files.uploadedfile import SimpleUploadedFile

from import_polon.forms import NowyImportForm, validate_polon_headers

# ============================================================================
# ZATRUDNIENIE field validation tests
# ============================================================================


@pytest.mark.django_db
def test_zatrudnienie_validation_valid_university_name(uczelnia):
    """Test that records with valid university names in ZATRUDNIENIE are processed"""
    from import_polon.core.import_polon import (
        validate_zatrudnienie_starts_with_university,
    )

    # Test with exact university name
    is_valid, matched_name = validate_zatrudnienie_starts_with_university(
        uczelnia.nazwa
    )
    assert is_valid is True
    assert matched_name == uczelnia.nazwa

    # Test with university name plus additional text (common pattern)
    zatrudnienie_with_details = (
        f"{uczelnia.nazwa} (Nauczyciel akademicki>Pracownik badawczo-dydaktyczny)"
    )
    is_valid, matched_name = validate_zatrudnienie_starts_with_university(
        zatrudnienie_with_details
    )
    assert is_valid is True
    assert matched_name == uczelnia.nazwa


@pytest.mark.django_db
def test_zatrudnienie_validation_invalid_employment_ignored():
    """Test that records with ZATRUDNIENIE not starting with university name
    are ignored"""
    from import_polon.core.import_polon import (
        validate_zatrudnienie_starts_with_university,
    )

    # Test with invalid university name
    is_valid, matched_name = validate_zatrudnienie_starts_with_university(
        "Inna Uczelnia XYZ"
    )
    assert is_valid is False
    assert matched_name is None

    # Test with partial match (should not match)
    is_valid, matched_name = validate_zatrudnienie_starts_with_university(
        "Przyrodniczy w Lublinie"
    )
    assert is_valid is False
    assert matched_name is None


@pytest.mark.django_db
def test_zatrudnienie_validation_empty_field_ignored():
    """Test that records with empty ZATRUDNIENIE field are ignored"""
    from import_polon.core.import_polon import (
        validate_zatrudnienie_starts_with_university,
    )

    # Test with None
    is_valid, matched_name = validate_zatrudnienie_starts_with_university(None)
    assert is_valid is False
    assert matched_name is None

    # Test with empty string
    is_valid, matched_name = validate_zatrudnienie_starts_with_university("")
    assert is_valid is False
    assert matched_name is None

    # Test with whitespace only
    is_valid, matched_name = validate_zatrudnienie_starts_with_university("   ")
    assert is_valid is False
    assert matched_name is None


# ============================================================================
# Header validation tests
# ============================================================================


@pytest.mark.django_db
def test_validate_polon_headers_valid_file(tmp_path):
    """Test that validate_polon_headers accepts files with all required headers"""
    # Create test data with all required headers
    test_data = {
        "NAZWISKO": ["Kowalski"],
        "IMIE": ["Jan"],
        "ZATRUDNIENIE": ["Test University"],
        "OSWIADCZENIE_N": ["nie"],
        "OSWIADCZENIE_O_DYSCYPLINACH": ["nie"],
        "ZATRUDNIENIE_OD": ["2023-01-01"],
        "ZATRUDNIENIE_DO": ["2023-12-31"],
        "WIELKOSC_ETATU_PREZENTACJA_DZIESIETNA": ["1.0"],
        "PROCENTOWY_UDZIAL_PIERWSZA_DYSCYPLINA": ["100.0"],
        "DYSCYPLINA_N": [""],
        "DYSCYPLINA_N_KOLEJNA": [""],
        "OSWIADCZONA_DYSCYPLINA_PIERWSZA": [""],
        "OSWIADCZONA_DYSCYPLINA_DRUGA": [""],
    }

    df = pd.DataFrame(test_data)
    test_file = tmp_path / "test_valid_headers.xlsx"
    df.to_excel(test_file, index=False)

    # Test validation
    missing_headers = validate_polon_headers(str(test_file))
    assert missing_headers == []


@pytest.mark.django_db
def test_validate_polon_headers_missing_headers(tmp_path):
    """Test that validate_polon_headers detects missing required headers"""
    # Create test data with missing required headers
    test_data = {
        "NAZWISKO": ["Kowalski"],
        "IMIE": ["Jan"],
        # Missing ZATRUDNIENIE and other required headers
    }

    df = pd.DataFrame(test_data)
    test_file = tmp_path / "test_missing_headers.xlsx"
    df.to_excel(test_file, index=False)

    # Test validation
    missing_headers = validate_polon_headers(str(test_file))
    assert len(missing_headers) > 0
    assert "ZATRUDNIENIE" in missing_headers
    assert "OSWIADCZENIE_N" in missing_headers


@pytest.mark.django_db
def test_validate_polon_headers_case_insensitive(tmp_path):
    """Test that header validation is case insensitive"""
    # Create test data with lowercase headers
    test_data = {
        "nazwisko": ["Kowalski"],
        "imie": ["Jan"],
        "zatrudnienie": ["Test University"],
        "oswiadczenie_n": ["nie"],
        "oswiadczenie_o_dyscyplinach": ["nie"],
        "zatrudnienie_od": ["2023-01-01"],
        "zatrudnienie_do": ["2023-12-31"],
        "wielkosc_etatu_prezentacja_dziesietna": ["1.0"],
        "procentowy_udzial_pierwsza_dyscyplina": ["100.0"],
        "dyscyplina_n": [""],
        "dyscyplina_n_kolejna": [""],
        "oswiadczona_dyscyplina_pierwsza": [""],
        "oswiadczona_dyscyplina_druga": [""],
    }

    df = pd.DataFrame(test_data)
    test_file = tmp_path / "test_lowercase_headers.xlsx"
    df.to_excel(test_file, index=False)

    # Test validation - should pass despite lowercase headers
    missing_headers = validate_polon_headers(str(test_file))
    assert missing_headers == []


# ============================================================================
# Form validation tests
# ============================================================================


@pytest.mark.django_db
def test_form_validation_with_invalid_headers(tmp_path):
    """Test that form validation rejects files with missing headers"""
    # Create test data with missing required headers
    test_data = {
        "NAZWISKO": ["Kowalski"],
        "IMIE": ["Jan"],
        # Missing most required headers
    }

    df = pd.DataFrame(test_data)
    test_file = tmp_path / "test_invalid_form.xlsx"
    df.to_excel(test_file, index=False)

    # Read file content
    with open(test_file, "rb") as f:
        file_content = f.read()

    # Create uploaded file
    uploaded_file = SimpleUploadedFile(
        "test_invalid_form.xlsx",
        file_content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    # Test form validation
    form_data = {
        "rok": 2023,
        "zapisz_zmiany_do_bazy": False,
        "ukryj_niezmatchowanych_autorow": False,
    }
    file_data = {"plik": uploaded_file}

    form = NowyImportForm(data=form_data, files=file_data)
    assert not form.is_valid()
    assert "plik" in form.errors
    assert "nie zawiera wymaganych nagłówków" in form.errors["plik"][0]
