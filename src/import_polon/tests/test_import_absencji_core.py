import pytest
from model_bakery import baker

from bpp.models import Autor
from import_polon.core import analyze_file_import_absencji
from import_polon.forms import validate_absencje_headers
from import_polon.models import ImportPlikuAbsencji


@pytest.mark.django_db
def test_analyze_excel_file_import_absencji(fn_test_import_absencji):
    ipa = baker.make(ImportPlikuAbsencji, zapisz_zmiany_do_bazy=True)

    jan_kowalski: Autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski")
    jan_kowalski.autor_absencja_set.create(rok=2017, ile_dni=50)

    adam_nowak: Autor = baker.make(
        Autor, nazwisko="Nowak", imiona="Adam", orcid="0001-0009-3366-100X"
    )
    adam_nowak_2: Autor = baker.make(Autor, nazwisko="Nowak", imiona="Adam")

    analyze_file_import_absencji(fn_test_import_absencji, ipa)

    assert jan_kowalski.autor_absencja_set.get(rok=2017).ile_dni == 141
    assert jan_kowalski.autor_absencja_set.get(rok=2018).ile_dni == 352

    assert adam_nowak.autor_absencja_set.get(rok=2020).ile_dni == 100
    assert adam_nowak_2.autor_absencja_set.count() == 0


@pytest.mark.django_db
def test_analyze_excel_file_import_absencji_zly_plik(fn_test_import_polon):
    ipa = baker.make(ImportPlikuAbsencji, zapisz_zmiany_do_bazy=True)

    analyze_file_import_absencji(fn_test_import_polon, ipa)


@pytest.mark.django_db
def test_validate_absencje_headers_valid_file(tmp_path):
    """Test that validate_absencje_headers accepts files with all required headers"""
    import pandas as pd

    # Create test data with all required headers
    test_data = {
        "NAZWISKO": ["Kowalski"],
        "IMIE": ["Jan"],
        "ROK_NIEOBECNOSC": ["2023 - 10"],
    }

    df = pd.DataFrame(test_data)
    test_file = tmp_path / "test_valid_absencje_headers.xlsx"
    df.to_excel(test_file, index=False)

    # Test validation
    missing_headers = validate_absencje_headers(str(test_file))
    assert missing_headers == []


@pytest.mark.django_db
def test_validate_absencje_headers_missing_headers(tmp_path):
    """Test that validate_absencje_headers detects missing required headers"""
    import pandas as pd

    # Create test data with missing required headers
    test_data = {
        "NAZWISKO": ["Kowalski"],
        "IMIE": ["Jan"],
        # Missing ROK_NIEOBECNOSC
    }

    df = pd.DataFrame(test_data)
    test_file = tmp_path / "test_missing_absencje_headers.xlsx"
    df.to_excel(test_file, index=False)

    # Test validation
    missing_headers = validate_absencje_headers(str(test_file))
    assert len(missing_headers) > 0
    assert "ROK_NIEOBECNOSC" in missing_headers


@pytest.mark.django_db
def test_validate_absencje_headers_case_insensitive(tmp_path):
    """Test that header validation is case insensitive"""
    import pandas as pd

    # Create test data with lowercase headers
    test_data = {
        "nazwisko": ["Kowalski"],
        "imie": ["Jan"],
        "rok_nieobecnosc": ["2023 - 10"],
    }

    df = pd.DataFrame(test_data)
    test_file = tmp_path / "test_lowercase_absencje_headers.xlsx"
    df.to_excel(test_file, index=False)

    # Test validation - should pass despite lowercase headers
    missing_headers = validate_absencje_headers(str(test_file))
    assert missing_headers == []


@pytest.mark.django_db
def test_validate_absencje_headers_with_optional_headers(tmp_path):
    """Test that validation works with optional headers present"""
    import pandas as pd

    # Create test data with required and optional headers
    test_data = {
        "NAZWISKO": ["Kowalski"],
        "IMIE": ["Jan"],
        "ROK_NIEOBECNOSC": ["2023 - 10"],
        "ORCID": ["0000-0000-0000-0000"],
    }

    df = pd.DataFrame(test_data)
    test_file = tmp_path / "test_optional_absencje_headers.xlsx"
    df.to_excel(test_file, index=False)

    # Test validation - should pass with optional headers
    missing_headers = validate_absencje_headers(str(test_file))
    assert missing_headers == []


@pytest.mark.django_db
def test_absencje_form_validation_with_invalid_headers(tmp_path):
    """Test that absences form validation rejects files with missing headers"""
    import pandas as pd
    from django.core.files.uploadedfile import SimpleUploadedFile

    from import_polon.forms import NowyImportAbsencjiForm

    # Create test data with missing required headers
    test_data = {
        "NAZWISKO": ["Kowalski"],
        "IMIE": ["Jan"],
        # Missing ROK_NIEOBECNOSC
    }

    df = pd.DataFrame(test_data)
    test_file = tmp_path / "test_invalid_absencje_form.xlsx"
    df.to_excel(test_file, index=False)

    # Read file content
    with open(test_file, "rb") as f:
        file_content = f.read()

    # Create uploaded file
    uploaded_file = SimpleUploadedFile(
        "test_invalid_absencje_form.xlsx",
        file_content,
        content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    )

    # Test form validation
    form_data = {
        "zapisz_zmiany_do_bazy": False,
    }
    file_data = {"plik": uploaded_file}

    form = NowyImportAbsencjiForm(data=form_data, files=file_data)
    assert not form.is_valid()
    assert "plik" in form.errors
    assert "nie zawiera wymaganych nagłówków" in form.errors["plik"][0]
