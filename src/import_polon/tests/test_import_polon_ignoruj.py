"""
Tests for ignoruj_miejsce_pracy functionality in POLON import.

When ignoruj_miejsce_pracy=True, records with invalid ZATRUDNIENIE
(different university) are still processed instead of being skipped.
"""

import pandas as pd
import pytest
from django.core.files import File
from model_bakery import baker

from bpp.models import Autor
from import_polon.core.import_polon import analyze_file_import_polon
from import_polon.models import ImportPlikuPolon, WierszImportuPlikuPolon


@pytest.mark.django_db
def test_analyze_file_import_polon_ignoruj_miejsce_pracy_true(tmp_path, uczelnia):
    """Test that with ignoruj_miejsce_pracy=True, records with invalid
    ZATRUDNIENIE are processed"""
    # Create test data with invalid ZATRUDNIENIE (different university)
    test_data = {
        "IMIE": ["Jan", "Anna"],
        "NAZWISKO": ["Kowalski", "Nowak"],
        "ZATRUDNIENIE": ["Inna Uczelnia", "Uniwersytet XYZ"],
        "ORCID": ["", ""],
        "OSWIADCZENIE_N": ["nie", "nie"],
        "OSWIADCZENIE_O_DYSCYPLINACH": ["nie", "nie"],
    }

    df = pd.DataFrame(test_data)
    test_file = tmp_path / "test_ignoruj_miejsce_pracy.xlsx"
    df.to_excel(test_file, index=False)

    # Create import model with ignoruj_miejsce_pracy=True
    import_model = baker.make(
        ImportPlikuPolon,
        rok=2023,
        zapisz_zmiany_do_bazy=False,
        ukryj_niezmatchowanych_autorow=False,
        ignoruj_miejsce_pracy=True,  # Key setting for this test
    )

    with open(test_file, "rb") as f:
        import_model.plik.save("test_ignoruj_miejsce_pracy.xlsx", File(f))

    # Run import
    analyze_file_import_polon(str(test_file), import_model)

    # Check results - records should NOT be ignored due to ZATRUDNIENIE
    results = WierszImportuPlikuPolon.objects.filter(parent=import_model)
    assert results.count() == 2

    for result in results:
        # Records should NOT have "REKORD ZIGNOROWANY" message about ZATRUDNIENIE
        assert "nie zaczyna się od nazwy żadnej uczelni" not in result.rezultat


@pytest.mark.django_db
def test_analyze_file_import_polon_ignoruj_miejsce_pracy_false_default(
    tmp_path, uczelnia
):
    """Test that with ignoruj_miejsce_pracy=False (default), records are skipped"""
    # Create test data with invalid ZATRUDNIENIE
    test_data = {
        "IMIE": ["Jan"],
        "NAZWISKO": ["Kowalski"],
        "ZATRUDNIENIE": ["Inna Uczelnia"],
        "ORCID": [""],
        "OSWIADCZENIE_N": ["nie"],
        "OSWIADCZENIE_O_DYSCYPLINACH": ["nie"],
    }

    df = pd.DataFrame(test_data)
    test_file = tmp_path / "test_ignoruj_miejsce_pracy_false.xlsx"
    df.to_excel(test_file, index=False)

    # Create import model with ignoruj_miejsce_pracy=False (default)
    import_model = baker.make(
        ImportPlikuPolon,
        rok=2023,
        zapisz_zmiany_do_bazy=False,
        ignoruj_miejsce_pracy=False,  # Explicitly set to False (default behavior)
    )

    with open(test_file, "rb") as f:
        import_model.plik.save("test_ignoruj_miejsce_pracy_false.xlsx", File(f))

    # Run import
    analyze_file_import_polon(str(test_file), import_model)

    # Check results - record should be ignored
    results = WierszImportuPlikuPolon.objects.filter(parent=import_model)
    assert results.count() == 1

    result = results.first()
    assert "REKORD ZIGNOROWANY" in result.rezultat
    assert "nie zaczyna się od nazwy żadnej uczelni" in result.rezultat


@pytest.mark.django_db
def test_analyze_file_import_polon_ignoruj_miejsce_pracy_processes_author(
    tmp_path, uczelnia, dyscyplina1, rodzaj_autora_z
):
    """Test that with ignoruj_miejsce_pracy=True, author matching still works"""
    # Create author that should be matched
    autor = baker.make(Autor, imiona="Jan", nazwisko="Testowy")

    # Create test data with invalid ZATRUDNIENIE but matching author
    test_data = {
        "IMIE": ["Jan"],
        "NAZWISKO": ["Testowy"],
        "ZATRUDNIENIE": ["Inna Uczelnia"],  # Invalid - different university
        "ORCID": [""],
        "OSWIADCZENIE_N": ["nie"],
        "OSWIADCZENIE_O_DYSCYPLINACH": ["tak"],
        "GRUPA_STANOWISK": ["Pracownik dydaktyczny"],
        "ZATRUDNIENIE_OD": ["2023-01-01"],
        "ZATRUDNIENIE_DO": ["2023-12-31"],
        "WIELKOSC_ETATU_PREZENTACJA_DZIESIETNA": ["1.0"],
        "PROCENTOWY_UDZIAL_PIERWSZA_DYSCYPLINA": ["100.0"],
        "DYSCYPLINA_N": [""],
        "DYSCYPLINA_N_KOLEJNA": [""],
        "OSWIADCZONA_DYSCYPLINA_PIERWSZA": [dyscyplina1.nazwa],
        "OSWIADCZONA_DYSCYPLINA_DRUGA": [""],
    }

    df = pd.DataFrame(test_data)
    test_file = tmp_path / "test_ignoruj_autor.xlsx"
    df.to_excel(test_file, index=False)

    # Create import model with ignoruj_miejsce_pracy=True
    import_model = baker.make(
        ImportPlikuPolon,
        rok=2023,
        zapisz_zmiany_do_bazy=True,
        ignoruj_miejsce_pracy=True,
    )

    with open(test_file, "rb") as f:
        import_model.plik.save("test_ignoruj_autor.xlsx", File(f))

    # Run import
    analyze_file_import_polon(str(test_file), import_model)

    # Check that author was matched and processed
    results = WierszImportuPlikuPolon.objects.filter(parent=import_model)
    assert results.count() == 1

    result = results.first()
    assert result.autor == autor
    assert "REKORD ZIGNOROWANY" not in result.rezultat

    # Verify author discipline was created
    ad = autor.autor_dyscyplina_set.filter(rok=2023).first()
    assert ad is not None
    assert ad.dyscyplina_naukowa == dyscyplina1
