from unittest.mock import Mock, patch

import pytest
from model_bakery import baker

from bpp.models import Zrodlo
from import_list_ministerialnych.core import (
    analyze_excel_file_import_list_ministerialnych,
    detect_duplicates,
)
from import_list_ministerialnych.models import ImportListMinisterialnych
from pbn_api.models import Journal


@pytest.mark.django_db
def test_import_list_ministerialnych_with_mnisw_id():
    """Test import matching journals by mniswId when ISSN is missing"""

    # Create a PBN Journal with mniswId
    pbn_journal = Journal.objects.create(
        mongoId="test_journal_98765",
        status="ACTIVE",
        verificationLevel="VERIFIED",
        verified=True,
        versions=[
            {
                "current": True,
                "object": {"title": "Test PBN Journal", "mniswId": 98765},
            }
        ],
        mniswId=98765,
        title="Test PBN Journal",
    )

    # Create a Zrodlo linked to this PBN Journal
    zrodlo = baker.make(Zrodlo, nazwa="Test Journal", pbn_uid=pbn_journal)

    # Create parent import model
    parent_model = baker.make(
        ImportListMinisterialnych,
        rok=2023,
        zapisz_zmiany_do_bazy=True,
        importuj_punktacje=True,
        importuj_dyscypliny=False,
        ignoruj_zrodla_bez_odpowiednika=False,
    )
    parent_model.send_progress = Mock()

    # Mock Excel data with mniswId but no ISSN
    mock_data = [
        {
            "Tytul_1": "Wrong Title",
            "Tytul_2": None,
            "issn": None,
            "issn.1": None,
            "e-issn": None,
            "e-issn.1": None,
            "Unikatowy Identyfikator Czasopisma": 98765,
            "Punkty": 100,
        }
    ]

    # Patch the Excel reading function
    with patch(
        "import_list_ministerialnych.core.wczytaj_plik_importu_dyscyplin_zrodel",
        return_value=mock_data,
    ):
        with patch("import_list_ministerialnych.core.napraw_literowki_w_bazie"):
            analyze_excel_file_import_list_ministerialnych("dummy.xlsx", parent_model)

    # Check that the journal was matched and punktacja was set
    assert zrodlo.punktacja_zrodla_set.filter(rok=2023).exists()
    punktacja = zrodlo.punktacja_zrodla_set.get(rok=2023)
    assert punktacja.punkty_kbn == 100

    # Check that import row was created with correct journal
    wiersz = parent_model.wierszimportulistyministerialnej_set.first()
    assert wiersz.zrodlo == zrodlo


@pytest.mark.django_db
def test_import_list_ministerialnych_issn_priority():
    """Test that ISSN matching takes priority over mniswId"""

    # Create two different journals
    pbn_journal1 = Journal.objects.create(
        mongoId="test_journal_issn_11111",
        status="ACTIVE",
        verificationLevel="VERIFIED",
        verified=True,
        versions=[
            {
                "current": True,
                "object": {"title": "Journal by mniswId", "mniswId": 11111},
            }
        ],
        mniswId=11111,
        title="Journal by mniswId",
    )
    baker.make(
        Zrodlo, nazwa="Journal by mniswId", pbn_uid=pbn_journal1
    )  # Created but should not match

    zrodlo2 = baker.make(Zrodlo, nazwa="Journal by ISSN", issn="2222-2222")

    # Create parent import model
    parent_model = baker.make(
        ImportListMinisterialnych,
        rok=2023,
        zapisz_zmiany_do_bazy=True,
        importuj_punktacje=True,
        importuj_dyscypliny=False,
        ignoruj_zrodla_bez_odpowiednika=False,
    )
    parent_model.send_progress = Mock()

    # Mock Excel data with both ISSN and mniswId
    mock_data = [
        {
            "Tytul_1": "Some Title",
            "Tytul_2": None,
            "issn": "2222-2222",  # This should match zrodlo2
            "issn.1": None,
            "e-issn": None,
            "e-issn.1": None,
            "Unikatowy Identyfikator Czasopisma": 11111,  # This would match zrodlo1
            "Punkty": 140,
        }
    ]

    with patch(
        "import_list_ministerialnych.core.wczytaj_plik_importu_dyscyplin_zrodel",
        return_value=mock_data,
    ):
        with patch("import_list_ministerialnych.core.napraw_literowki_w_bazie"):
            analyze_excel_file_import_list_ministerialnych("dummy.xlsx", parent_model)

    # Should match by ISSN (zrodlo2), not by mniswId (zrodlo1)
    wiersz = parent_model.wierszimportulistyministerialnej_set.first()
    assert wiersz.zrodlo == zrodlo2


@pytest.mark.django_db
def test_import_list_ministerialnych_no_mnisw_id():
    """Test import when mniswId is missing or None"""

    zrodlo = baker.make(Zrodlo, nazwa="Journal by Title", issn="3333-3333")

    parent_model = baker.make(
        ImportListMinisterialnych,
        rok=2023,
        zapisz_zmiany_do_bazy=True,
        importuj_punktacje=True,
        importuj_dyscypliny=False,
        ignoruj_zrodla_bez_odpowiednika=False,
    )
    parent_model.send_progress = Mock()

    # Mock Excel data without mniswId column
    mock_data = [
        {
            "Tytul_1": "Journal by Title",
            "Tytul_2": None,
            "issn": "3333-3333",
            "issn.1": None,
            "e-issn": None,
            "e-issn.1": None,
            # No "Unikatowy Identyfikator Czasopisma" key
            "Punkty": 70,
        }
    ]

    with patch(
        "import_list_ministerialnych.core.wczytaj_plik_importu_dyscyplin_zrodel",
        return_value=mock_data,
    ):
        with patch("import_list_ministerialnych.core.napraw_literowki_w_bazie"):
            analyze_excel_file_import_list_ministerialnych("dummy.xlsx", parent_model)

    # Should still match by ISSN
    wiersz = parent_model.wierszimportulistyministerialnej_set.first()
    assert wiersz.zrodlo == zrodlo


@pytest.mark.django_db
def test_import_list_ministerialnych_invalid_mnisw_id():
    """Test import when mniswId is invalid (non-numeric)"""

    zrodlo = baker.make(Zrodlo, nazwa="Valid Journal", e_issn="4444-4444")

    parent_model = baker.make(
        ImportListMinisterialnych,
        rok=2023,
        zapisz_zmiany_do_bazy=True,
        importuj_punktacje=True,
        importuj_dyscypliny=False,
        ignoruj_zrodla_bez_odpowiednika=False,
    )
    parent_model.send_progress = Mock()

    mock_data = [
        {
            "Tytul_1": "Valid Journal",
            "Tytul_2": None,
            "issn": None,
            "issn.1": None,
            "e-issn": "4444-4444",
            "e-issn.1": None,
            "Unikatowy Identyfikator Czasopisma": "not-a-number",  # Invalid
            "Punkty": 200,
        }
    ]

    with patch(
        "import_list_ministerialnych.core.wczytaj_plik_importu_dyscyplin_zrodel",
        return_value=mock_data,
    ):
        with patch("import_list_ministerialnych.core.napraw_literowki_w_bazie"):
            analyze_excel_file_import_list_ministerialnych("dummy.xlsx", parent_model)

    # Should fall back to e-issn matching
    wiersz = parent_model.wierszimportulistyministerialnej_set.first()
    assert wiersz.zrodlo == zrodlo


@pytest.mark.django_db
def test_import_list_ministerialnych_column_name_with_space():
    """Test import when column name has leading space"""

    pbn_journal = Journal.objects.create(
        mongoId="test_journal_space_55555",
        status="ACTIVE",
        verificationLevel="VERIFIED",
        verified=True,
        versions=[
            {
                "current": True,
                "object": {"title": "Space Column Journal", "mniswId": 55555},
            }
        ],
        mniswId=55555,
        title="Space Column Journal",
    )
    zrodlo = baker.make(Zrodlo, nazwa="Space Column Journal", pbn_uid=pbn_journal)

    parent_model = baker.make(
        ImportListMinisterialnych,
        rok=2023,
        zapisz_zmiany_do_bazy=True,
        importuj_punktacje=True,
        importuj_dyscypliny=False,
        ignoruj_zrodla_bez_odpowiednika=False,
    )
    parent_model.send_progress = Mock()

    # Mock Excel data with space in column name (common Excel issue)
    mock_data = [
        {
            "Tytul_1": "Some Title",
            "Tytul_2": None,
            "issn": None,
            "issn.1": None,
            "e-issn": None,
            "e-issn.1": None,
            " Unikatowy Identyfikator Czasopisma": 55555,  # Note the leading space
            "Punkty": 80,
        }
    ]

    with patch(
        "import_list_ministerialnych.core.wczytaj_plik_importu_dyscyplin_zrodel",
        return_value=mock_data,
    ):
        with patch("import_list_ministerialnych.core.napraw_literowki_w_bazie"):
            analyze_excel_file_import_list_ministerialnych("dummy.xlsx", parent_model)

    # Should still match by mniswId despite space in column name
    wiersz = parent_model.wierszimportulistyministerialnej_set.first()
    assert wiersz.zrodlo == zrodlo


def test_detect_duplicates():
    """Test the duplicate detection function"""

    # Test data with duplicates
    data = [
        {
            "Tytul_1": "Journal A",
            "issn": "1111-1111",
            "e-issn": None,
            "Unikatowy Identyfikator Czasopisma": 111,
            "Punkty": 100,
        },
        {
            "Tytul_1": "Journal A Copy",
            "issn": "1111-1111",  # Duplicate ISSN
            "e-issn": None,
            "Unikatowy Identyfikator Czasopisma": 222,
            "Punkty": 140,
        },
        {
            "Tytul_1": "Journal B",
            "issn": "2222-2222",
            "e-issn": "2222-EEEE",
            "Unikatowy Identyfikator Czasopisma": 333,
            "Punkty": 70,
        },
        {
            "Tytul_1": "Journal C",
            "issn": None,
            "e-issn": "2222-EEEE",  # Duplicate E-ISSN
            "Unikatowy Identyfikator Czasopisma": 444,
            "Punkty": 100,
        },
        {
            "Tytul_1": "Journal D",
            "issn": None,
            "e-issn": None,
            "Unikatowy Identyfikator Czasopisma": 111,  # Duplicate mniswId
            "Punkty": 50,
        },
    ]

    duplicates = detect_duplicates(data)

    # Row 4 (index 1 in data, row 4 in Excel) should be duplicate of row 3 by ISSN
    assert 4 in duplicates
    assert duplicates[4]["duplicate_of"] == 3
    assert "ISSN" in duplicates[4]["reasons"]

    # Row 6 (index 3 in data) should be duplicate of row 5 by E-ISSN
    assert 6 in duplicates
    assert duplicates[6]["duplicate_of"] == 5
    assert "E-ISSN" in duplicates[6]["reasons"]

    # Row 7 (index 4 in data) should be duplicate of row 3 by mniswId
    assert 7 in duplicates
    assert duplicates[7]["duplicate_of"] == 3
    assert "mniswId" in duplicates[7]["reasons"]


@pytest.mark.django_db
def test_import_with_duplicate_detection():
    """Test that duplicates are properly marked during import"""

    # Create a Zrodlo for matching
    baker.make(Zrodlo, nazwa="Journal A", issn="1111-1111")  # Will be matched by import

    # Create parent import model
    parent_model = baker.make(
        ImportListMinisterialnych,
        rok=2023,
        zapisz_zmiany_do_bazy=True,
        importuj_punktacje=True,
        importuj_dyscypliny=False,
        ignoruj_zrodla_bez_odpowiednika=False,
    )
    parent_model.send_progress = Mock()

    # Mock data with duplicate ISSN
    mock_data = [
        {
            "Tytul_1": "Journal A",
            "Tytul_2": None,
            "issn": "1111-1111",
            "issn.1": None,
            "e-issn": None,
            "e-issn.1": None,
            "Unikatowy Identyfikator Czasopisma": 111,
            "Punkty": 100,
        },
        {
            "Tytul_1": "Journal A Duplicate",
            "Tytul_2": None,
            "issn": "1111-1111",  # Same ISSN
            "issn.1": None,
            "e-issn": None,
            "e-issn.1": None,
            "Unikatowy Identyfikator Czasopisma": 222,  # Different mniswId
            "Punkty": 140,
        },
    ]

    with patch(
        "import_list_ministerialnych.core.wczytaj_plik_importu_dyscyplin_zrodel",
        return_value=mock_data,
    ):
        with patch("import_list_ministerialnych.core.napraw_literowki_w_bazie"):
            analyze_excel_file_import_list_ministerialnych("dummy.xlsx", parent_model)

    # Check that two rows were created
    assert parent_model.wierszimportulistyministerialnej_set.count() == 2

    # First row should not be marked as duplicate
    first_row = parent_model.wierszimportulistyministerialnej_set.get(nr_wiersza=3)
    assert first_row.is_duplicate is False
    assert first_row.duplicate_of_row is None

    # Second row should be marked as duplicate
    second_row = parent_model.wierszimportulistyministerialnej_set.get(nr_wiersza=4)
    assert second_row.is_duplicate is True
    assert second_row.duplicate_of_row == 3
    assert "ISSN" in second_row.duplicate_reason
    assert "DUPLIKAT" in second_row.rezultat


@pytest.mark.django_db
def test_import_with_multiple_duplicate_reasons():
    """Test when a journal is duplicate by multiple identifiers"""

    parent_model = baker.make(
        ImportListMinisterialnych,
        rok=2023,
        zapisz_zmiany_do_bazy=False,
        importuj_punktacje=False,
        importuj_dyscypliny=False,
        ignoruj_zrodla_bez_odpowiednika=False,
    )
    parent_model.send_progress = Mock()

    mock_data = [
        {
            "Tytul_1": "Journal A",
            "Tytul_2": None,
            "issn": "1111-1111",
            "issn.1": None,
            "e-issn": "1111-EEEE",
            "e-issn.1": None,
            "Unikatowy Identyfikator Czasopisma": 111,
            "Punkty": 100,
        },
        {
            "Tytul_1": "Journal A Complete Duplicate",
            "Tytul_2": None,
            "issn": "1111-1111",  # Same ISSN
            "issn.1": None,
            "e-issn": "1111-EEEE",  # Same E-ISSN
            "e-issn.1": None,
            "Unikatowy Identyfikator Czasopisma": 111,  # Same mniswId
            "Punkty": 100,
        },
    ]

    with patch(
        "import_list_ministerialnych.core.wczytaj_plik_importu_dyscyplin_zrodel",
        return_value=mock_data,
    ):
        with patch("import_list_ministerialnych.core.napraw_literowki_w_bazie"):
            analyze_excel_file_import_list_ministerialnych("dummy.xlsx", parent_model)

    # Second row should have all three duplicate reasons
    second_row = parent_model.wierszimportulistyministerialnej_set.get(nr_wiersza=4)
    assert second_row.is_duplicate is True
    assert "ISSN" in second_row.duplicate_reason
    assert "E-ISSN" in second_row.duplicate_reason
    assert "mniswId" in second_row.duplicate_reason


@pytest.mark.django_db
def test_import_results_view_filtering(admin_client, admin_user):
    """Test filtering functionality in results view"""
    from import_list_ministerialnych.models import WierszImportuListyMinisterialnej

    # Create parent import model
    parent_model = baker.make(
        ImportListMinisterialnych,
        rok=2023,
        zapisz_zmiany_do_bazy=False,
        importuj_punktacje=False,
        importuj_dyscypliny=False,
        finished_successfully=True,
        owner=admin_user,  # Set owner to admin_user
    )

    # Create test rows with different results
    baker.make(
        WierszImportuListyMinisterialnej,
        parent=parent_model,
        nr_wiersza=1,
        rezultat="Punktacja identyczna w BPP i w XLS",
        is_duplicate=False,
    )
    baker.make(
        WierszImportuListyMinisterialnej,
        parent=parent_model,
        nr_wiersza=2,
        rezultat="Dyscypliny zgodne w BPP i w XLSX",
        is_duplicate=False,
    )
    baker.make(
        WierszImportuListyMinisterialnej,
        parent=parent_model,
        nr_wiersza=3,
        rezultat="DUPLIKAT wiersza 1 (ISSN). Some other text",
        is_duplicate=True,
        duplicate_of_row=1,
        duplicate_reason="ISSN",
    )
    baker.make(
        WierszImportuListyMinisterialnej,
        parent=parent_model,
        nr_wiersza=4,
        rezultat="Ustawiam punktację 100",
        is_duplicate=False,
    )

    # Test no filters - should show all 4 rows
    response = admin_client.get(
        f"/import_list_ministerialnych/{parent_model.pk}/results/"
    )
    assert response.status_code == 200
    assert response.context["total_count"] == 4
    assert response.context["duplicate_count"] == 1
    assert response.context["identical_punkty_count"] == 1
    assert response.context["identical_dyscypliny_count"] == 1

    # Test exclude identical punkty
    response = admin_client.get(
        f"/import_list_ministerialnych/{parent_model.pk}/results/?exclude_identical_punkty=1"
    )
    assert response.status_code == 200
    # Should exclude row 1
    assert len(response.context["object_list"]) == 3

    # Test exclude identical dyscypliny
    response = admin_client.get(
        f"/import_list_ministerialnych/{parent_model.pk}/results/?exclude_identical_dyscypliny=1"
    )
    assert response.status_code == 200
    # Should exclude row 2
    assert len(response.context["object_list"]) == 3

    # Test only duplicates
    response = admin_client.get(
        f"/import_list_ministerialnych/{parent_model.pk}/results/?only_duplicates=1"
    )
    assert response.status_code == 200
    # Should show only row 3
    assert len(response.context["object_list"]) == 1
    assert response.context["object_list"][0].is_duplicate is True

    # Test multiple filters combined
    response = admin_client.get(
        f"/import_list_ministerialnych/{parent_model.pk}/results/"
        f"?exclude_identical_punkty=1&exclude_identical_dyscypliny=1"
    )
    assert response.status_code == 200
    # Should exclude rows 1 and 2, showing 3 and 4
    assert len(response.context["object_list"]) == 2


@pytest.mark.django_db
def test_import_with_nie_porownuj_po_tytulach_enabled():
    """Test that when nie_porownuj_po_tytulach=True, matching only uses ISSN/E-ISSN/mniswId"""

    # Create sources with similar names but different IDs
    zrodlo_electronics = baker.make(  # noqa
        Zrodlo, nazwa="Electronics", issn="1111-1111"
    )  # noqa
    zrodlo_electronics_switzerland = baker.make(
        Zrodlo, nazwa="Electronics (Switzerland)", issn="2222-2222"
    )

    # Create parent import model with nie_porownuj_po_tytulach=True
    parent_model = baker.make(
        ImportListMinisterialnych,
        rok=2023,
        zapisz_zmiany_do_bazy=False,
        importuj_punktacje=False,
        importuj_dyscypliny=False,
        ignoruj_zrodla_bez_odpowiednika=False,
        nie_porownuj_po_tytulach=True,  # Enable the new option
    )
    parent_model.send_progress = Mock()

    # Mock Excel data with title "Electronics" but ISSN matching "Electronics (Switzerland)"
    mock_data = [
        {
            "Tytul_1": "Electronics",  # This title matches zrodlo_electronics
            "Tytul_2": None,
            "issn": "2222-2222",  # But ISSN matches zrodlo_electronics_switzerland
            "issn.1": None,
            "e-issn": None,
            "e-issn.1": None,
            "Unikatowy Identyfikator Czasopisma": None,
            "Punkty": 100,
        }
    ]

    with patch(
        "import_list_ministerialnych.core.wczytaj_plik_importu_dyscyplin_zrodel",
        return_value=mock_data,
    ):
        with patch("import_list_ministerialnych.core.napraw_literowki_w_bazie"):
            analyze_excel_file_import_list_ministerialnych("dummy.xlsx", parent_model)

    # Should match by ISSN (zrodlo_electronics_switzerland), NOT by title (zrodlo_electronics)
    wiersz = parent_model.wierszimportulistyministerialnej_set.first()
    assert wiersz.zrodlo == zrodlo_electronics_switzerland


@pytest.mark.django_db
def test_import_with_nie_porownuj_po_tytulach_disabled():
    """Test that when nie_porownuj_po_tytulach=False (default), title matching works"""

    # Create a source with only a title (no ISSN)
    zrodlo = baker.make(Zrodlo, nazwa="Test Journal")

    # Create parent import model with nie_porownuj_po_tytulach=False (default)
    parent_model = baker.make(
        ImportListMinisterialnych,
        rok=2023,
        zapisz_zmiany_do_bazy=False,
        importuj_punktacje=False,
        importuj_dyscypliny=False,
        ignoruj_zrodla_bez_odpowiednika=False,
        nie_porownuj_po_tytulach=False,  # Default behavior - use title matching
    )
    parent_model.send_progress = Mock()

    # Mock Excel data with matching title but no ISSN
    mock_data = [
        {
            "Tytul_1": "Test Journal",
            "Tytul_2": None,
            "issn": None,
            "issn.1": None,
            "e-issn": None,
            "e-issn.1": None,
            "Unikatowy Identyfikator Czasopisma": None,
            "Punkty": 100,
        }
    ]

    with patch(
        "import_list_ministerialnych.core.wczytaj_plik_importu_dyscyplin_zrodel",
        return_value=mock_data,
    ):
        with patch("import_list_ministerialnych.core.napraw_literowki_w_bazie"):
            analyze_excel_file_import_list_ministerialnych("dummy.xlsx", parent_model)

    # Should match by title since nie_porownuj_po_tytulach=False
    wiersz = parent_model.wierszimportulistyministerialnej_set.first()
    assert wiersz.zrodlo == zrodlo


@pytest.mark.django_db
def test_import_title_not_matched_when_nie_porownuj_po_tytulach_enabled():
    """Test that title matching is truly skipped when nie_porownuj_po_tytulach=True"""

    # Create a source with only a title (no ISSN, E-ISSN, or mniswId)
    baker.make(Zrodlo, nazwa="Title Only Journal")

    # Create parent import model with nie_porownuj_po_tytulach=True
    parent_model = baker.make(
        ImportListMinisterialnych,
        rok=2023,
        zapisz_zmiany_do_bazy=False,
        importuj_punktacje=False,
        importuj_dyscypliny=False,
        ignoruj_zrodla_bez_odpowiednika=False,
        nie_porownuj_po_tytulach=True,  # Skip title matching
    )
    parent_model.send_progress = Mock()

    # Mock Excel data with matching title but no identifiers
    mock_data = [
        {
            "Tytul_1": "Title Only Journal",  # This matches the source by title
            "Tytul_2": None,
            "issn": None,  # No ISSN
            "issn.1": None,
            "e-issn": None,  # No E-ISSN
            "e-issn.1": None,
            "Unikatowy Identyfikator Czasopisma": None,  # No mniswId
            "Punkty": 100,
        }
    ]

    with patch(
        "import_list_ministerialnych.core.wczytaj_plik_importu_dyscyplin_zrodel",
        return_value=mock_data,
    ):
        with patch("import_list_ministerialnych.core.napraw_literowki_w_bazie"):
            analyze_excel_file_import_list_ministerialnych("dummy.xlsx", parent_model)

    # Should NOT match because title matching is disabled and no IDs are provided
    wiersz = parent_model.wierszimportulistyministerialnej_set.first()
    assert wiersz.zrodlo is None
    assert "Brak takiego źródła po stronie BPP" in wiersz.rezultat


@pytest.mark.django_db
def test_import_results_view_statistics(admin_client, admin_user):
    """Test that statistics are calculated correctly"""
    from import_list_ministerialnych.models import WierszImportuListyMinisterialnej

    parent_model = baker.make(
        ImportListMinisterialnych,
        rok=2023,
        finished_successfully=True,
        owner=admin_user,
    )

    # Create 10 rows with various combinations
    for i in range(3):
        baker.make(
            WierszImportuListyMinisterialnej,
            parent=parent_model,
            nr_wiersza=i * 3 + 1,
            rezultat="Punktacja identyczna w BPP i w XLS",
            is_duplicate=False,
        )

    for i in range(2):
        baker.make(
            WierszImportuListyMinisterialnej,
            parent=parent_model,
            nr_wiersza=i * 3 + 10,
            rezultat="Dyscypliny zgodne w BPP i w XLSX",
            is_duplicate=False,
        )

    for i in range(4):
        baker.make(
            WierszImportuListyMinisterialnej,
            parent=parent_model,
            nr_wiersza=i * 3 + 20,
            rezultat=f"DUPLIKAT wiersza {i} (ISSN)",
            is_duplicate=True,
            duplicate_of_row=i,
        )

    baker.make(
        WierszImportuListyMinisterialnej,
        parent=parent_model,
        nr_wiersza=30,
        rezultat="Some other result",
        is_duplicate=False,
    )

    response = admin_client.get(
        f"/import_list_ministerialnych/{parent_model.pk}/results/"
    )
    assert response.status_code == 200

    # Verify statistics
    assert response.context["total_count"] == 10
    assert response.context["duplicate_count"] == 4
    assert response.context["identical_punkty_count"] == 3
    assert response.context["identical_dyscypliny_count"] == 2
