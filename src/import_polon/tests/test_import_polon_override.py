"""
Tests for ImportPolonOverride (wymuszenie) functionality.

These tests verify that the override mechanism for position groups works correctly
when determining author types (B - badawczy, Z - non-research).
"""

import pandas as pd
import pytest
from django.core.files import File
from model_bakery import baker

from bpp.models import Autor
from import_polon.core.import_polon import analyze_file_import_polon
from import_polon.models import ImportPlikuPolon, ImportPolonOverride


@pytest.mark.django_db
def test_import_polon_override_badawczy_true(
    tmp_path, uczelnia, dyscyplina1, rodzaj_autora_b, rodzaj_autora_z
):
    """Test that ImportPolonOverride with jest_badawczy=True marks author as
    type 'B' (wymuszenie)"""
    # Create override for a custom position group
    ImportPolonOverride.objects.create(
        grupa_stanowisk="Pracownik dydaktyczny", jest_badawczy=True
    )

    # Create test data with custom position group
    test_data = {
        "IMIE": ["Jan"],
        "NAZWISKO": ["Testowy"],
        "ZATRUDNIENIE": [f"{uczelnia.nazwa}"],
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
    test_file = tmp_path / "test_override_true.xlsx"
    df.to_excel(test_file, index=False)

    # Create author
    autor = baker.make(Autor, imiona="Jan", nazwisko="Testowy")

    # Create import model
    import_model = baker.make(ImportPlikuPolon, rok=2023, zapisz_zmiany_do_bazy=True)

    with open(test_file, "rb") as f:
        import_model.plik.save("test_override_true.xlsx", File(f))

    # Run import
    analyze_file_import_polon(str(test_file), import_model)

    # Check if author was classified as type 'B' due to override
    ad = autor.autor_dyscyplina_set.get(rok=2023)
    assert ad.rodzaj_autora == rodzaj_autora_b


@pytest.mark.django_db
def test_import_polon_override_badawczy_false(
    tmp_path, uczelnia, dyscyplina1, rodzaj_autora_b, rodzaj_autora_z
):
    """Test that ImportPolonOverride with jest_badawczy=False marks author as
    type 'Z' (wymuszenie)"""
    # Create wymuszenie that prevents marking as badawczy
    ImportPolonOverride.objects.create(
        grupa_stanowisk="Pracownik badawczo-dydaktyczny", jest_badawczy=False
    )

    # Create test data with normally badawczy position (but overridden)
    test_data = {
        "IMIE": ["Anna"],
        "NAZWISKO": ["Testowa"],
        "ZATRUDNIENIE": [f"{uczelnia.nazwa}"],
        "ORCID": [""],
        "OSWIADCZENIE_N": ["nie"],
        "OSWIADCZENIE_O_DYSCYPLINACH": ["tak"],
        "GRUPA_STANOWISK": ["Pracownik badawczo-dydaktyczny"],
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
    test_file = tmp_path / "test_override_false.xlsx"
    df.to_excel(test_file, index=False)

    # Create author
    autor = baker.make(Autor, imiona="Anna", nazwisko="Testowa")

    # Create import model
    import_model = baker.make(ImportPlikuPolon, rok=2023, zapisz_zmiany_do_bazy=True)

    with open(test_file, "rb") as f:
        import_model.plik.save("test_override_false.xlsx", File(f))

    # Run import
    analyze_file_import_polon(str(test_file), import_model)

    # Check if author was classified as type 'Z' (not B) due to wymuszenie
    ad = autor.autor_dyscyplina_set.get(rok=2023)
    assert ad.rodzaj_autora == rodzaj_autora_z


@pytest.mark.django_db
def test_import_polon_no_override_uses_default_logic(
    tmp_path, uczelnia, dyscyplina1, rodzaj_autora_b, rodzaj_autora_z
):
    """Test that without wymuszenie, default hardcoded logic is used"""
    # No wymuszenie created - should use default logic

    # Create test data with default badawczy position
    test_data = {
        "IMIE": ["Piotr"],
        "NAZWISKO": ["Testowy"],
        "ZATRUDNIENIE": [f"{uczelnia.nazwa}"],
        "ORCID": [""],
        "OSWIADCZENIE_N": ["nie"],
        "OSWIADCZENIE_O_DYSCYPLINACH": ["tak"],
        "GRUPA_STANOWISK": ["Pracownik badawczo-dydaktyczny"],
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
    test_file = tmp_path / "test_no_override.xlsx"
    df.to_excel(test_file, index=False)

    # Create author
    autor = baker.make(Autor, imiona="Piotr", nazwisko="Testowy")

    # Create import model
    import_model = baker.make(ImportPlikuPolon, rok=2023, zapisz_zmiany_do_bazy=True)

    with open(test_file, "rb") as f:
        import_model.plik.save("test_no_override.xlsx", File(f))

    # Run import
    analyze_file_import_polon(str(test_file), import_model)

    # Check if author was classified as type 'B' using default logic
    ad = autor.autor_dyscyplina_set.get(rok=2023)
    assert ad.rodzaj_autora == rodzaj_autora_b


@pytest.mark.django_db
def test_import_polon_override_case_insensitive(
    tmp_path, uczelnia, dyscyplina1, rodzaj_autora_b, rodzaj_autora_z
):
    """Test that ImportPolonOverride matching is case-insensitive (wymuszenie)"""
    # Create override with lowercase
    ImportPolonOverride.objects.create(
        grupa_stanowisk="pracownik administracyjny", jest_badawczy=True
    )

    # Create test data with different case
    test_data = {
        "IMIE": ["Maria"],
        "NAZWISKO": ["Testowa"],
        "ZATRUDNIENIE": [f"{uczelnia.nazwa}"],
        "ORCID": [""],
        "OSWIADCZENIE_N": ["nie"],
        "OSWIADCZENIE_O_DYSCYPLINACH": ["tak"],
        "GRUPA_STANOWISK": ["PRACOWNIK ADMINISTRACYJNY"],
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
    test_file = tmp_path / "test_override_case.xlsx"
    df.to_excel(test_file, index=False)

    # Create author
    autor = baker.make(Autor, imiona="Maria", nazwisko="Testowa")

    # Create import model
    import_model = baker.make(ImportPlikuPolon, rok=2023, zapisz_zmiany_do_bazy=True)

    with open(test_file, "rb") as f:
        import_model.plik.save("test_override_case.xlsx", File(f))

    # Run import
    analyze_file_import_polon(str(test_file), import_model)

    # Check if author was classified as type 'B' despite different case
    ad = autor.autor_dyscyplina_set.get(rok=2023)
    assert ad.rodzaj_autora == rodzaj_autora_b
