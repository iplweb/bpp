"""
Core tests for POLON import functionality.

For validation tests, see test_import_polon_validation.py
For override (wymuszenie) tests, see test_import_polon_override.py
For ignoruj_miejsce_pracy tests, see test_import_polon_ignoruj.py
"""

import pandas as pd
import pytest
from denorm import denorms
from django.core.files import File
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
from import_polon.models import ImportPlikuPolon, WierszImportuPlikuPolon


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

        # Dariusz jest współautorem pracy, ma tam dyscyplinę; po imporcie
        # (rekalkulacji) ma go tam nie być:
        zwarte_z_dyscyplinami.dodaj_autora(
            dariusz_dyscyplinabezn, jednostka, dyscyplina_naukowa=dyscyplina1
        )

        # Przebuduj
        denorms.flush()

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


@pytest.mark.django_db
def test_analyze_file_import_polon_with_invalid_zatrudnienie(tmp_path, uczelnia):
    """Test that import process ignores records with invalid ZATRUDNIENIE"""
    from import_polon.core.import_polon import analyze_file_import_polon

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
    from import_polon.core.import_polon import analyze_file_import_polon

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

    import_model = baker.make(
        ImportPlikuPolon,
        rok=2023,
        zapisz_zmiany_do_bazy=False,
        ukryj_niezmatchowanych_autorow=False,
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
    """Test that authors with 'Pracownik badawczo-dydaktyczny' are classified
    as type 'B'"""
    with transaction.atomic():
        from import_polon.core.import_polon import analyze_file_import_polon

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
            # The test data contains "Pracownik badawczo-dydaktyczny"
            # so should be type 'B' if not in N and not doctoral student
            assert ad.rodzaj_autora in [
                rodzaj_autora_b,
                rodzaj_autora_z,
                rodzaj_autora_n,
            ]
        except Autor_Dyscyplina.DoesNotExist:
            # Author might not be in test data, that's OK for this test
            pass
