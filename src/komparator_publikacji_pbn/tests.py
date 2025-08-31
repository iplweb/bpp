import pytest
from django.test import Client
from django.urls import reverse
from model_bakery import baker

from pbn_api.models import Publication

from bpp.models import Wydawnictwo_Ciagle, Wydawnictwo_Zwarte


@pytest.mark.django_db
def test_publication_comparison_view_requires_login():
    """Test that the view requires user to be logged in."""
    client = Client()
    url = reverse("komparator_publikacji_pbn:comparison_list")
    response = client.get(url)
    assert response.status_code == 302  # Redirect to login


@pytest.mark.django_db
def test_publication_comparison_view_requires_staff(admin_user, normal_django_user):
    """Test that the view requires staff status."""
    client = Client()
    url = reverse("komparator_publikacji_pbn:comparison_list")

    # Normal user should be redirected
    client.force_login(normal_django_user)
    response = client.get(url)
    assert response.status_code == 302

    # Admin user should have access
    client.force_login(admin_user)
    response = client.get(url)
    assert response.status_code == 200


@pytest.mark.django_db
def test_publication_comparison_view_empty(admin_user):
    """Test view when no publications with pbn_uid exist."""
    client = Client()
    client.force_login(admin_user)

    url = reverse("komparator_publikacji_pbn:comparison_list")
    response = client.get(url)

    assert response.status_code == 200
    assert len(response.context["comparisons"]) == 0


@pytest.mark.django_db
def test_publication_comparison_view_with_matching_data(admin_user):
    """Test view with publications that have matching PBN data."""
    client = Client()
    client.force_login(admin_user)

    # Create PBN publication
    pbn_pub = baker.make(
        Publication,
        mongoId="test123",
        title="Test Publication",
        year=2023,
        doi="10.1234/test",
        status="ACTIVE",
        versions=[
            {
                "current": True,
                "object": {
                    "title": "Test Publication",
                    "year": 2023,
                    "doi": "10.1234/test",
                },
            }
        ],
    )

    # Create BPP publication with matching data
    bpp_pub = baker.make(  # noqa
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Test Publication",
        rok=2023,
        doi="10.1234/test",
        pbn_uid=pbn_pub,
    )

    url = reverse("komparator_publikacji_pbn:comparison_list")
    response = client.get(url)

    assert response.status_code == 200
    # Should not show publications with no differences
    assert len(response.context["comparisons"]) == 0


@pytest.mark.django_db
def test_publication_comparison_view_with_differences(admin_user):
    """Test view with publications that have differences."""
    client = Client()
    client.force_login(admin_user)

    # Create PBN publication
    pbn_pub = baker.make(
        Publication,
        mongoId="test456",
        title="PBN Title",
        year=2023,
        doi="10.1234/pbn",
        status="ACTIVE",
        versions=[
            {
                "current": True,
                "object": {"title": "PBN Title", "year": 2023, "doi": "10.1234/pbn"},
            }
        ],
    )

    # Create BPP publication with different data
    bpp_pub = baker.make(  # noqa
        Wydawnictwo_Ciagle,
        tytul_oryginalny="BPP Title Different",
        rok=2023,
        doi="10.1234/bpp",
        pbn_uid=pbn_pub,
    )

    url = reverse("komparator_publikacji_pbn:comparison_list")
    # Test with all fields enabled (default)
    response = client.get(url)

    assert response.status_code == 200
    comparisons = response.context["comparisons"]
    assert len(comparisons) == 1

    # Check that differences were detected
    comparison = comparisons[0]
    assert comparison["has_differences"] is True
    assert len(comparison["differences"]) > 0

    # Check specific differences
    field_names = [d["field"] for d in comparison["differences"]]
    assert "Tytuł" in field_names
    assert "DOI" in field_names


@pytest.mark.django_db
def test_publication_comparison_view_filtering_by_type(admin_user):
    """Test filtering by publication type."""
    client = Client()
    client.force_login(admin_user)

    # Create PBN publications
    pbn_ciagle = baker.make(
        Publication,
        mongoId="ciagle123",
        title="Ciągłe PBN",
        year=2023,
        status="ACTIVE",
        versions=[{"current": True, "object": {"title": "Ciągłe PBN Different"}}],
    )

    pbn_zwarte = baker.make(
        Publication,
        mongoId="zwarte123",
        title="Zwarte PBN",
        year=2023,
        status="ACTIVE",
        versions=[{"current": True, "object": {"title": "Zwarte PBN Different"}}],
    )

    # Create BPP publications with differences
    baker.make(
        Wydawnictwo_Ciagle, tytul_oryginalny="Ciągłe BPP", rok=2023, pbn_uid=pbn_ciagle
    )

    baker.make(
        Wydawnictwo_Zwarte, tytul_oryginalny="Zwarte BPP", rok=2023, pbn_uid=pbn_zwarte
    )

    # Test filtering for ciągłe only
    url = reverse("komparator_publikacji_pbn:comparison_list")
    response = client.get(url, {"type": "ciagle"})
    assert response.status_code == 200
    comparisons = response.context["comparisons"]
    assert len(comparisons) == 1
    assert comparisons[0]["type"] == "ciagle"

    # Test filtering for zwarte only
    response = client.get(url, {"type": "zwarte"})
    assert response.status_code == 200
    comparisons = response.context["comparisons"]
    assert len(comparisons) == 1
    assert comparisons[0]["type"] == "zwarte"

    # Test showing all
    response = client.get(url, {"type": "all"})
    assert response.status_code == 200
    comparisons = response.context["comparisons"]
    assert len(comparisons) == 2


@pytest.mark.django_db
def test_publication_comparison_view_search(admin_user):
    """Test search functionality."""
    client = Client()
    client.force_login(admin_user)

    # Create PBN publications
    pbn1 = baker.make(
        Publication,
        mongoId="search1",
        title="Searchable Title",
        doi="10.1234/searchable",
        status="ACTIVE",
        versions=[{"current": True, "object": {"title": "Different Title"}}],
    )

    pbn2 = baker.make(
        Publication,
        mongoId="search2",
        title="Other Publication",
        doi="10.1234/other",
        status="ACTIVE",
        versions=[{"current": True, "object": {"title": "Very Different"}}],
    )

    # Create BPP publications
    baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Searchable Publication",
        doi="10.1234/search",
        rok=2023,  # Within default year range
        pbn_uid=pbn1,
    )

    baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Not Matching",
        doi="10.1234/nomatch",
        rok=2023,  # Within default year range
        pbn_uid=pbn2,
    )

    url = reverse("komparator_publikacji_pbn:comparison_list")

    # Search by title
    response = client.get(url, {"q": "Searchable"})
    assert response.status_code == 200
    comparisons = response.context["comparisons"]
    assert len(comparisons) == 1

    # Search by DOI
    response = client.get(url, {"q": "10.1234/search"})
    assert response.status_code == 200
    comparisons = response.context["comparisons"]
    assert len(comparisons) == 1


@pytest.mark.django_db
def test_publication_comparison_pagination(admin_user):
    """Test pagination works correctly."""
    client = Client()
    client.force_login(admin_user)

    # Create more than 5 publications with differences (paginate_by = 5)
    for i in range(8):
        pbn_pub = baker.make(
            Publication,
            mongoId=f"pag{i}",
            title=f"PBN Title {i}",
            year=2023,
            status="ACTIVE",
            versions=[{"current": True, "object": {"title": f"PBN Title {i}"}}],
        )

        baker.make(
            Wydawnictwo_Ciagle,
            tytul_oryginalny=f"BPP Title Different {i}",
            rok=2023,
            pbn_uid=pbn_pub,
        )

    url = reverse("komparator_publikacji_pbn:comparison_list")

    # First page
    response = client.get(url)
    assert response.status_code == 200
    assert len(response.context["comparisons"]) == 5
    assert response.context["is_paginated"] is True

    # Second page
    response = client.get(url, {"page": 2})
    assert response.status_code == 200
    assert len(response.context["comparisons"]) == 3


@pytest.mark.django_db
def test_publication_comparison_isbn_for_books(admin_user):
    """Test ISBN comparison for books."""
    client = Client()
    client.force_login(admin_user)

    # Create PBN book publication
    pbn_book = baker.make(
        Publication,
        mongoId="book123",
        title="Book Title",
        isbn="978-83-1234567-8-9",
        year=2023,
        status="ACTIVE",
        versions=[
            {
                "current": True,
                "object": {"title": "Book Title", "isbn": "978-83-1234567-8-9"},
            }
        ],
    )

    # Create BPP book with different ISBN
    baker.make(
        Wydawnictwo_Zwarte,
        tytul_oryginalny="Book Title",
        isbn="978-83-9876543-2-1",
        rok=2023,
        pbn_uid=pbn_book,
    )

    url = reverse("komparator_publikacji_pbn:comparison_list")
    response = client.get(url)

    assert response.status_code == 200
    comparisons = response.context["comparisons"]
    assert len(comparisons) == 1

    # Check ISBN difference is detected
    comparison = comparisons[0]
    field_names = [d["field"] for d in comparison["differences"]]
    assert "ISBN" in field_names


@pytest.mark.django_db
def test_publication_comparison_author_count(admin_user):
    """Test author count comparison."""
    client = Client()
    client.force_login(admin_user)

    # Create PBN publication with authors
    pbn_pub = baker.make(
        Publication,
        mongoId="authors123",
        title="Publication with Authors",
        year=2023,
        status="ACTIVE",
        versions=[
            {
                "current": True,
                "object": {
                    "title": "Publication with Authors",
                    "authors": [
                        {"name": "Author 1"},
                        {"name": "Author 2"},
                        {"name": "Author 3"},
                    ],
                },
            }
        ],
    )

    # Create BPP publication with different number of authors
    bpp_pub = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Publication with Authors",
        rok=2023,
        pbn_uid=pbn_pub,
    )

    # Add only 2 authors to BPP publication
    autor1 = baker.make("bpp.Autor")
    autor2 = baker.make("bpp.Autor")
    baker.make(
        "bpp.Wydawnictwo_Ciagle_Autor", rekord=bpp_pub, autor=autor1, kolejnosc=0
    )
    baker.make(
        "bpp.Wydawnictwo_Ciagle_Autor", rekord=bpp_pub, autor=autor2, kolejnosc=1
    )

    url = reverse("komparator_publikacji_pbn:comparison_list")
    response = client.get(url)

    assert response.status_code == 200
    comparisons = response.context["comparisons"]
    assert len(comparisons) == 1

    # Check author count difference is detected
    comparison = comparisons[0]
    field_names = [d["field"] for d in comparison["differences"]]
    assert "Liczba autorów" in field_names


@pytest.mark.django_db
def test_year_filtering(admin_user):
    """Test year min/max filtering."""
    client = Client()
    client.force_login(admin_user)

    # Create publications in different years
    for year in [2020, 2023, 2026]:
        pbn_pub = baker.make(
            Publication,
            mongoId=f"year{year}",
            title=f"Publication {year}",
            year=year,
            status="ACTIVE",
            versions=[{"current": True, "object": {"title": f"Different {year}"}}],
        )

        baker.make(
            Wydawnictwo_Ciagle,
            tytul_oryginalny=f"Publication {year}",
            rok=year,
            pbn_uid=pbn_pub,
        )

    url = reverse("komparator_publikacji_pbn:comparison_list")

    # Test default filter (2022-2025)
    response = client.get(url)
    assert response.status_code == 200
    comparisons = response.context["comparisons"]
    assert len(comparisons) == 1  # Only 2023 publication

    # Test custom year range
    response = client.get(url, {"year_min": 2020, "year_max": 2023})
    assert response.status_code == 200
    comparisons = response.context["comparisons"]
    assert len(comparisons) == 2  # 2020 and 2023 publications


@pytest.mark.django_db
def test_field_selection(admin_user):
    """Test selecting which fields to compare."""
    client = Client()
    client.force_login(admin_user)

    # Create PBN publication
    pbn_pub = baker.make(
        Publication,
        mongoId="fields123",
        title="PBN Title",
        year=2023,
        doi="10.1234/pbn",
        status="ACTIVE",
        versions=[
            {
                "current": True,
                "object": {"title": "PBN Title", "year": 2023, "doi": "10.1234/pbn"},
            }
        ],
    )

    # Create BPP publication with different data
    bpp_pub = baker.make(  # noqa
        Wydawnictwo_Ciagle,
        tytul_oryginalny="BPP Title Different",
        rok=2023,
        doi="10.1234/bpp",
        pbn_uid=pbn_pub,
    )

    url = reverse("komparator_publikacji_pbn:comparison_list")

    # Test comparing only title
    response = client.get(url, {"fields": ["title"]})
    assert response.status_code == 200
    comparisons = response.context["comparisons"]
    assert len(comparisons) == 1
    comparison = comparisons[0]
    field_names = [d["field"] for d in comparison["differences"]]
    assert "Tytuł" in field_names
    assert "DOI" not in field_names  # DOI should not be compared

    # Test comparing only DOI
    response = client.get(url, {"fields": ["doi"]})
    comparisons = response.context["comparisons"]
    assert len(comparisons) == 1
    comparison = comparisons[0]
    field_names = [d["field"] for d in comparison["differences"]]
    assert "DOI" in field_names
    assert "Tytuł" not in field_names  # Title should not be compared


@pytest.mark.django_db
def test_xlsx_export(admin_user):
    """Test XLSX export functionality."""
    client = Client()
    client.force_login(admin_user)

    # Create test data
    pbn_pub = baker.make(
        Publication,
        mongoId="export123",
        title="Export Test",
        year=2023,
        doi="10.1234/export",
        status="ACTIVE",
        versions=[{"current": True, "object": {"title": "Different Title"}}],
    )

    baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Export Test",
        rok=2023,
        doi="10.1234/test",
        pbn_uid=pbn_pub,
    )

    url = reverse("komparator_publikacji_pbn:comparison_list")
    response = client.get(url, {"export": "xlsx"})

    assert response.status_code == 200
    assert (
        response["Content-Type"]
        == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )
    assert (
        'attachment; filename="komparator_publikacji_bpp_pbn.xlsx"'
        in response["Content-Disposition"]
    )
