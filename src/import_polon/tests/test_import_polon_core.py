import pytest
from denorm import denorms
from django.db import transaction
from model_bakery import baker

from import_polon.core import analyze_file_import_polon
from import_polon.models import ImportPlikuPolon

from bpp.models import (
    Autor,
    Autor_Dyscyplina,
    Cache_Punktacja_Autora,
    Rekord,
    Wydawnictwo_Zwarte,
)


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
            rodzaj_autora=Autor_Dyscyplina.RODZAJE_AUTORA.N,
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
            rodzaj_autora=Autor_Dyscyplina.RODZAJE_AUTORA.Z,
        )

        analyze_file_import_polon(fn_test_import_polon, ipp)

        assert (
            artur_dyscyplinazn.autor_dyscyplina_set.get(rok=ROK).rodzaj_autora
            == Autor_Dyscyplina.RODZAJE_AUTORA.N
        )
        assert (
            artur_dyscyplinazn.autor_dyscyplina_set.get(rok=ROK).dyscyplina_naukowa
            == dyscyplina1
        )

        assert (
            dariusz_dyscyplinabezn.autor_dyscyplina_set.get(rok=ROK).rodzaj_autora
            == Autor_Dyscyplina.RODZAJE_AUTORA.Z
        )

        assert (
            stanislaw_dyscyplinazn.autor_dyscyplina_set.get(rok=ROK).rodzaj_autora
            == Autor_Dyscyplina.RODZAJE_AUTORA.N
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
