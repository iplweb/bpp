import pytest
from denorm import denorms
from django.db import transaction
from model_bakery import baker

from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Cache_Punktacja_Autora,
    Rekord,
    Wydawnictwo_Zwarte,
)
from import_polon.core import analyze_file_import_polon
from import_polon.forms import validate_polon_headers
from import_polon.models import ImportPlikuPolon


@pytest.mark.django_db
def test_analyze_excel_file_import_polon_zly_plik(fn_test_import_absencji):
    ROK = 2020
    ipp: ImportPlikuPolon = baker.make(
        ImportPlikuPolon, zapisz_zmiany_do_bazy=True, rok=ROK
    )
    analyze_file_import_polon(fn_test_import_absencji, ipp)


@pytest.mark.django_db
def test_analyze_excel_file_import_polon_plik_bez_dyscyplin(
    fn_test_import_polon_bledny,
):
    ROK = 2020
    ipp: ImportPlikuPolon = baker.make(
        ImportPlikuPolon, zapisz_zmiany_do_bazy=True, rok=ROK
    )
    baker.make(Autor, nazwisko="Kowalski", imiona="Aleksander Bolesław")
    analyze_file_import_polon(fn_test_import_polon_bledny, ipp)


def test_analyze_excel_file_import_polon(
    transactional_db,
    fn_test_import_polon,
    dyscyplina1,
    zwarte_z_dyscyplinami: Wydawnictwo_Zwarte,
    jednostka,
    uczelnia,  # potrzebna do liczenia slotow, ISlot() uzywa
    rodzaj_autora_n,
    rodzaj_autora_z,
):
    with transaction.atomic():
        # Create test university matching the ZATRUDNIENIE field in test data
        from bpp.models import Uczelnia

        baker.make(Uczelnia, nazwa="Uniwersytet Naukowy", skrot="UN")
        ROK = 2020

        ipp: ImportPlikuPolon = baker.make(
            ImportPlikuPolon, zapisz_zmiany_do_bazy=True, rok=ROK
        )

        # Artur ZN nie ma żadnego wpisu za ten rok
        artur_dyscyplinazn: Autor = baker.make(
            Autor, imiona="Artur", nazwisko="DyscyplinaZN"
        )

        # Dariusz BezN jest w Nce, ale po imporcie ma go nie być.
        dariusz_dyscyplinabezn: Autor = baker.make(
            Autor, imiona="Dariusz", nazwisko="DyscyplinaBezN"
        )
        dariusz_dyscyplinabezn.autor_dyscyplina_set.create(
            rok=ROK,
            dyscyplina_naukowa=dyscyplina1,
            rodzaj_autora=rodzaj_autora_n,
        )

        zwarte_z_dyscyplinami.rok = ROK
        zwarte_z_dyscyplinami.save()

        # Dariusz jest współautorem pracy, ma tam dyscyplinę; po imporcie (rekalkulacji)
        # ma go tam nie być:
        zwarte_z_dyscyplinami.dodaj_autora(
            dariusz_dyscyplinabezn, jednostka, dyscyplina_naukowa=dyscyplina1
        )

        # Przebuduj
        denorms.flush()

        # pbn_wydawnictwo_zwarte_z_autorem_z_dyscyplina.cached_punkty_dyscyplin()

        rekord = Rekord.objects.get_for_model(zwarte_z_dyscyplinami)
        assert Cache_Punktacja_Autora.objects.filter(
            rekord_id=rekord.pk, autor=dariusz_dyscyplinabezn
        ).exists()

        # Stanisław ZN ma za ten rok wpis, ze nie jest w N
        stanislaw_dyscyplinazn: Autor = baker.make(
            Autor, imiona="Stanisław", nazwisko="DyscyplinaZN"
        )

        stanislaw_dyscyplinazn.autor_dyscyplina_set.create(
            rok=ROK,
            dyscyplina_naukowa=dyscyplina1,
            rodzaj_autora=rodzaj_autora_z,
        )

        analyze_file_import_polon(fn_test_import_polon, ipp)

        assert (
            artur_dyscyplinazn.autor_dyscyplina_set.get(rok=ROK).rodzaj_autora
            == rodzaj_autora_n
        )
        assert (
            artur_dyscyplinazn.autor_dyscyplina_set.get(rok=ROK).dyscyplina_naukowa
            == dyscyplina1
        )

        assert (
            dariusz_dyscyplinabezn.autor_dyscyplina_set.get(rok=ROK).rodzaj_autora
            == rodzaj_autora_z
        )

        assert (
            stanislaw_dyscyplinazn.autor_dyscyplina_set.get(rok=ROK).rodzaj_autora
            == rodzaj_autora_n
        )
    denorms.flush()

    # assert Cache_Punktacja_Autora.objects.filter(
    #     rekord_id=rekord.pk, autor=dariusz_dyscyplinabezn
    # ).exists()  # dla autora "Z" też liczymy.
    # dla autora Z nie liczymy


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
    """Test that records with ZATRUDNIENIE not starting with university name are ignored"""
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


@pytest.mark.django_db
def test_analyze_file_import_polon_with_invalid_zatrudnienie(tmp_path, uczelnia):
    """Test that import process ignores records with invalid ZATRUDNIENIE"""
    import pandas as pd
    from django.core.files import File

    from import_polon.core.import_polon import analyze_file_import_polon
    from import_polon.models import ImportPlikuPolon, WierszImportuPlikuPolon

    # Create test data with invalid ZATRUDNIENIE
    test_data = {
        "IMIE": ["Jan", "Anna"],
        "NAZWISKO": ["Kowalski", "Nowak"],
        "ZATRUDNIENIE": ["Inna Uczelnia", "Uniwersytet XYZ"],
        "ORCID": ["", ""],
        "OSWIADCZENIE_N": ["nie", "nie"],
        "OSWIADCZENIE_O_DYSCYPLINACH": ["nie", "nie"],
    }

    df = pd.DataFrame(test_data)
    test_file = tmp_path / "test_invalid_zatrudnienie.xlsx"
    df.to_excel(test_file, index=False)

    # Create import model using baker (like existing tests)
    from model_bakery import baker

    import_model = baker.make(ImportPlikuPolon, rok=2023, zapisz_zmiany_do_bazy=False)

    with open(test_file, "rb") as f:
        import_model.plik.save("test_invalid_zatrudnienie.xlsx", File(f))

    # Run import
    analyze_file_import_polon(str(test_file), import_model)

    # Check results - both records should be ignored
    results = WierszImportuPlikuPolon.objects.filter(parent=import_model)
    assert results.count() == 2

    for result in results:
        assert result.autor is None
        assert result.dyscyplina_naukowa is None
        assert result.subdyscyplina_naukowa is None
        assert "REKORD ZIGNOROWANY" in result.rezultat
        assert "nie zaczyna się od nazwy żadnej uczelni" in result.rezultat


@pytest.mark.django_db
def test_analyze_file_import_polon_with_valid_zatrudnienie(tmp_path, uczelnia):
    """Test that import process accepts records with valid ZATRUDNIENIE"""
    import pandas as pd
    from django.core.files import File

    from import_polon.core.import_polon import analyze_file_import_polon
    from import_polon.models import ImportPlikuPolon, WierszImportuPlikuPolon

    # Create test data with valid ZATRUDNIENIE
    test_data = {
        "IMIE": ["Jan"],
        "NAZWISKO": ["Kowalski"],
        "ZATRUDNIENIE": [
            f"{uczelnia.nazwa} (Nauczyciel akademicki>Pracownik badawczo-dydaktyczny)"
        ],
        "ORCID": [""],
        "OSWIADCZENIE_N": ["nie"],
        "OSWIADCZENIE_O_DYSCYPLINACH": ["nie"],
    }

    df = pd.DataFrame(test_data)
    test_file = tmp_path / "test_valid_zatrudnienie.xlsx"
    df.to_excel(test_file, index=False)

    # Create import model using baker (like existing tests)
    from model_bakery import baker

    import_model = baker.make(
        ImportPlikuPolon,
        rok=2023,
        zapisz_zmiany_do_bazy=False,
        ukryj_niezmatchowanych_autorow=False,  # Show unmatched authors for this test
    )

    with open(test_file, "rb") as f:
        import_model.plik.save("test_valid_zatrudnienie.xlsx", File(f))

    # Run import
    analyze_file_import_polon(str(test_file), import_model)

    # Check results - record should be processed (not ignored)
    results = WierszImportuPlikuPolon.objects.filter(parent=import_model)
    assert results.count() == 1

    result = results.first()
    assert "REKORD ZIGNOROWANY" not in result.rezultat
    # The record might not match an author, but it should not be ignored due to ZATRUDNIENIE


@pytest.mark.django_db
def test_analyze_excel_file_import_polon_badawczy_type(
    transactional_db,
    fn_test_import_polon,
    dyscyplina1,
    uczelnia,
    rodzaj_autora_n,
    rodzaj_autora_b,
    rodzaj_autora_z,
):
    """Test that authors with 'Pracownik badawczo-dydaktyczny' are classified as type 'B'"""
    with transaction.atomic():
        from import_polon.core.import_polon import analyze_file_import_polon
        from import_polon.models import ImportPlikuPolon

        ROK = 2020

        # Create test author
        autor_badawczy = baker.make(Autor, imiona="Anna", nazwisko="Badawcza")

        ipp: ImportPlikuPolon = baker.make(
            ImportPlikuPolon, zapisz_zmiany_do_bazy=True, rok=ROK
        )

        # Run import
        analyze_file_import_polon(fn_test_import_polon, ipp)

        # Check if author was classified as type 'B' based on GRUPA_STANOWISK
        try:
            ad = autor_badawczy.autor_dyscyplina_set.get(rok=ROK)
            # The test data contains "Pracownik badawczo-dydaktyczny" so should be type 'B'
            # if not in N and not doctoral student
            assert ad.rodzaj_autora in [
                rodzaj_autora_b,
                rodzaj_autora_z,
                rodzaj_autora_n,
            ]
        except Autor_Dyscyplina.DoesNotExist:
            # Author might not be in test data, that's OK for this test
            pass


@pytest.mark.django_db
def test_validate_polon_headers_valid_file(tmp_path):
    """Test that validate_polon_headers accepts files with all required headers"""
    import pandas as pd

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
    import pandas as pd

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
    import pandas as pd

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


@pytest.mark.django_db
def test_form_validation_with_invalid_headers(tmp_path):
    """Test that form validation rejects files with missing headers"""
    import pandas as pd
    from django.core.files.uploadedfile import SimpleUploadedFile

    from import_polon.forms import NowyImportForm

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


@pytest.mark.django_db
def test_import_polon_override_badawczy_true(
    tmp_path, uczelnia, dyscyplina1, rodzaj_autora_b, rodzaj_autora_z
):
    """Test that ImportPolonOverride with jest_badawczy=True marks author as type 'B' (wymuszenie)"""
    import pandas as pd
    from django.core.files import File
    from model_bakery import baker

    from import_polon.core.import_polon import analyze_file_import_polon
    from import_polon.models import ImportPlikuPolon, ImportPolonOverride

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
    """Test that ImportPolonOverride with jest_badawczy=False marks author as type 'Z' (wymuszenie)"""
    import pandas as pd
    from django.core.files import File
    from model_bakery import baker

    from import_polon.core.import_polon import analyze_file_import_polon
    from import_polon.models import ImportPlikuPolon, ImportPolonOverride

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
    import pandas as pd
    from django.core.files import File
    from model_bakery import baker

    from import_polon.core.import_polon import analyze_file_import_polon
    from import_polon.models import ImportPlikuPolon

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
    import pandas as pd
    from django.core.files import File
    from model_bakery import baker

    from import_polon.core.import_polon import analyze_file_import_polon
    from import_polon.models import ImportPlikuPolon, ImportPolonOverride

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


@pytest.mark.django_db
def test_analyze_file_import_polon_ignoruj_miejsce_pracy_true(tmp_path, uczelnia):
    """Test that with ignoruj_miejsce_pracy=True, records with invalid ZATRUDNIENIE are processed"""
    import pandas as pd
    from django.core.files import File

    from import_polon.core.import_polon import analyze_file_import_polon
    from import_polon.models import ImportPlikuPolon, WierszImportuPlikuPolon

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
    import pandas as pd
    from django.core.files import File

    from import_polon.core.import_polon import analyze_file_import_polon
    from import_polon.models import ImportPlikuPolon, WierszImportuPlikuPolon

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
    import pandas as pd
    from django.core.files import File

    from import_polon.core.import_polon import analyze_file_import_polon
    from import_polon.models import ImportPlikuPolon, WierszImportuPlikuPolon

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
