import pytest
from django.test import Client
from django.urls import reverse
from model_bakery import baker

from .models import PrzemapoaniePracAutora

from django.contrib.auth import get_user_model

from bpp.models import (
    Autor,
    Jednostka,
    Uczelnia,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
    Wydawnictwo_Zwarte,
    Wydawnictwo_Zwarte_Autor,
    Zrodlo,
)

User = get_user_model()


@pytest.fixture
def admin_user(db):
    """Create an admin user for tests"""
    return User.objects.create_user(
        username="testadmin", password="testpass", is_staff=True, is_superuser=True
    )


@pytest.fixture
def logged_in_admin_client(admin_user):
    """Create a logged in admin client"""
    client = Client()
    client.login(username="testadmin", password="testpass")
    return client


@pytest.fixture
def uczelnia(db):
    """Create a test university"""
    return baker.make(Uczelnia, nazwa="Test University")


@pytest.fixture
def jednostka_z(uczelnia):
    """Create source unit"""
    return baker.make(
        Jednostka, nazwa="Jednostka Źródłowa", skrot="JZ", uczelnia=uczelnia
    )


@pytest.fixture
def jednostka_do(uczelnia):
    """Create target unit"""
    return baker.make(
        Jednostka, nazwa="Jednostka Docelowa", skrot="JD", uczelnia=uczelnia
    )


@pytest.fixture
def autor(jednostka_do):
    """Create a test author"""
    return baker.make(
        Autor, imiona="Jan", nazwisko="Kowalski", aktualna_jednostka=jednostka_do
    )


@pytest.fixture
def zrodlo(db):
    """Create a test journal"""
    return baker.make(Zrodlo, nazwa="Test Journal", skrot="TJ")


@pytest.mark.django_db
def test_przemapowanie_stores_work_history(
    logged_in_admin_client, autor, jednostka_z, jednostka_do, zrodlo, admin_user
):
    """Test that remapping stores detailed history of works in JSON fields"""
    # Create works for the author in the source unit
    wydawnictwo_ciagle1 = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="First Article Title",
        rok=2023,
        zrodlo=zrodlo,
    )
    baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=wydawnictwo_ciagle1,
        autor=autor,
        jednostka=jednostka_z,
    )

    wydawnictwo_ciagle2 = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Second Article Title",
        rok=2024,
        zrodlo=zrodlo,
    )
    baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=wydawnictwo_ciagle2,
        autor=autor,
        jednostka=jednostka_z,
    )

    wydawnictwo_zwarte = baker.make(
        Wydawnictwo_Zwarte,
        tytul_oryginalny="Book Title",
        rok=2023,
        isbn="978-1234567890",
        wydawnictwo="Test Publisher",
    )
    baker.make(
        Wydawnictwo_Zwarte_Autor,
        rekord=wydawnictwo_zwarte,
        autor=autor,
        jednostka=jednostka_z,
    )

    # Perform the remapping
    url = reverse(
        "przemapuj_prace_autora:przemapuj_prace", kwargs={"autor_id": autor.pk}
    )
    response = logged_in_admin_client.post(
        url,
        {
            "jednostka_z": jednostka_z.pk,
            "jednostka_do": jednostka_do.pk,
            "confirm": "true",
        },
    )

    assert response.status_code == 302  # Redirect after success

    # Check that the history was saved
    log = PrzemapoaniePracAutora.objects.filter(autor=autor).first()
    assert log is not None

    # Verify the continuous works history
    assert len(log.prace_ciagle_historia) == 2

    # Check first article
    first_article = next(
        (p for p in log.prace_ciagle_historia if p["tytul"] == "First Article Title"),
        None,
    )
    assert first_article is not None
    assert first_article["id"] == wydawnictwo_ciagle1.id
    assert first_article["rok"] == 2023
    assert first_article["zrodlo"] == "Test Journal"

    # Check second article
    second_article = next(
        (p for p in log.prace_ciagle_historia if p["tytul"] == "Second Article Title"),
        None,
    )
    assert second_article is not None
    assert second_article["id"] == wydawnictwo_ciagle2.id
    assert second_article["rok"] == 2024

    # Verify the monograph works history
    assert len(log.prace_zwarte_historia) == 1

    book = log.prace_zwarte_historia[0]
    assert book["id"] == wydawnictwo_zwarte.id
    assert book["tytul"] == "Book Title"
    assert book["rok"] == 2023
    assert book["isbn"] == "978-1234567890"
    assert book["wydawnictwo"] == "Test Publisher"


@pytest.mark.django_db
def test_empty_history_when_no_works(
    logged_in_admin_client, autor, jednostka_z, jednostka_do, admin_user
):
    """Test that empty history is stored when there are no works to remap"""
    # Don't create any works, but try to remap anyway
    # (This shouldn't normally happen due to form validation, but test the edge case)

    # We need to create at least one work to pass validation
    wydawnictwo = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Dummy")
    baker.make(
        Wydawnictwo_Ciagle_Autor, rekord=wydawnictwo, autor=autor, jednostka=jednostka_z
    )

    url = reverse(
        "przemapuj_prace_autora:przemapuj_prace", kwargs={"autor_id": autor.pk}
    )
    response = logged_in_admin_client.post(
        url,
        {
            "jednostka_z": jednostka_z.pk,
            "jednostka_do": jednostka_do.pk,
            "confirm": "true",
        },
    )

    assert response.status_code == 302

    log = PrzemapoaniePracAutora.objects.filter(autor=autor).first()
    assert log is not None
    assert len(log.prace_ciagle_historia) == 1
    assert log.prace_zwarte_historia == []  # No monograph works


@pytest.mark.django_db
def test_admin_display_methods():
    """Test the admin display methods for history"""
    from .admin import PrzemapoaniePracAutoraAdmin

    # Create a log entry with some history
    log = baker.make(
        PrzemapoaniePracAutora,
        prace_ciagle_historia=[
            {"id": 1, "tytul": "Article 1", "rok": 2023, "zrodlo": "Journal A"},
            {"id": 2, "tytul": "Article 2", "rok": 2024, "zrodlo": None},
        ],
        prace_zwarte_historia=[
            {
                "id": 3,
                "tytul": "Book 1",
                "rok": 2023,
                "isbn": "123456",
                "wydawnictwo": "Publisher X",
            }
        ],
    )

    admin_instance = PrzemapoaniePracAutoraAdmin(PrzemapoaniePracAutora, None)

    # Test display of continuous works history
    ciagle_html = admin_instance.display_prace_ciagle_historia(log)
    assert "Article 1" in ciagle_html
    assert "Article 2" in ciagle_html
    assert "Journal A" in ciagle_html
    assert "Łącznie: 2 prac" in ciagle_html

    # Test display of monograph works history
    zwarte_html = admin_instance.display_prace_zwarte_historia(log)
    assert "Book 1" in zwarte_html
    assert "123456" in zwarte_html
    assert "Publisher X" in zwarte_html
    assert "Łącznie: 1 prac" in zwarte_html

    # Test empty history
    empty_log = baker.make(
        PrzemapoaniePracAutora, prace_ciagle_historia=[], prace_zwarte_historia=[]
    )

    assert admin_instance.display_prace_ciagle_historia(empty_log) == "Brak danych"
    assert admin_instance.display_prace_zwarte_historia(empty_log) == "Brak danych"
