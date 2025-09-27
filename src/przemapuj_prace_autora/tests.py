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
def jednostka_domyslna(uczelnia):
    """Create the default unit"""
    return baker.make(
        Jednostka, nazwa="Jednostka Domyślna", skrot="JD", uczelnia=uczelnia
    )


@pytest.fixture
def jednostka_docelowa(uczelnia):
    """Create a target unit"""
    return baker.make(
        Jednostka, nazwa="Jednostka Docelowa", skrot="JDocel", uczelnia=uczelnia
    )


@pytest.fixture
def autor(jednostka_docelowa):
    """Create a test author with current unit"""
    return baker.make(
        Autor, imiona="Jan", nazwisko="Kowalski", aktualna_jednostka=jednostka_docelowa
    )


@pytest.mark.django_db
def test_wybierz_autora_view_requires_login():
    """Test that the author selection view requires login"""
    client = Client()
    url = reverse("przemapuj_prace_autora:wybierz_autora")
    response = client.get(url)
    assert response.status_code == 302  # Redirect to login


@pytest.mark.django_db
def test_wybierz_autora_view_works_when_logged_in(logged_in_admin_client):
    """Test that the author selection view works when logged in"""
    url = reverse("przemapuj_prace_autora:wybierz_autora")
    response = logged_in_admin_client.get(url)
    assert response.status_code == 200
    assert "Przemapowanie prac autora między jednostkami" in str(
        response.content, "utf-8"
    )


@pytest.mark.django_db
def test_wybierz_autora_search(logged_in_admin_client, autor):
    """Test searching for authors"""
    url = reverse("przemapuj_prace_autora:wybierz_autora")
    response = logged_in_admin_client.get(url, {"q": "Kowalski"})
    assert response.status_code == 200
    assert "Kowalski" in str(response.content, "utf-8")


@pytest.mark.django_db
def test_przemapuj_prace_view_requires_login(autor):
    """Test that the remapping view requires login"""
    client = Client()
    url = reverse(
        "przemapuj_prace_autora:przemapuj_prace", kwargs={"autor_id": autor.pk}
    )
    response = client.get(url)
    assert response.status_code == 302  # Redirect to login


@pytest.mark.django_db
def test_przemapuj_prace_view_displays_author_info(logged_in_admin_client, autor):
    """Test that the remapping view displays author information"""
    url = reverse(
        "przemapuj_prace_autora:przemapuj_prace", kwargs={"autor_id": autor.pk}
    )
    response = logged_in_admin_client.get(url)
    assert response.status_code == 200
    assert "Kowalski Jan" in str(response.content, "utf-8")


@pytest.mark.django_db
def test_przemapuj_prace_with_works(
    logged_in_admin_client, autor, jednostka_domyslna, jednostka_docelowa, admin_user
):
    """Test remapping works from one unit to another"""
    # Create some works for the author in the default unit
    wydawnictwo_ciagle = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Test Article")
    baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=wydawnictwo_ciagle,
        autor=autor,
        jednostka=jednostka_domyslna,
    )

    wydawnictwo_zwarte = baker.make(Wydawnictwo_Zwarte, tytul_oryginalny="Test Book")
    baker.make(
        Wydawnictwo_Zwarte_Autor,
        rekord=wydawnictwo_zwarte,
        autor=autor,
        jednostka=jednostka_domyslna,
    )

    # Check initial state
    assert (
        Wydawnictwo_Ciagle_Autor.objects.filter(
            autor=autor, jednostka=jednostka_domyslna
        ).count()
        == 1
    )
    assert (
        Wydawnictwo_Zwarte_Autor.objects.filter(
            autor=autor, jednostka=jednostka_domyslna
        ).count()
        == 1
    )

    url = reverse(
        "przemapuj_prace_autora:przemapuj_prace", kwargs={"autor_id": autor.pk}
    )

    # First, preview the changes
    response = logged_in_admin_client.post(
        url,
        {
            "jednostka_z": jednostka_domyslna.pk,
            "jednostka_do": jednostka_docelowa.pk,
            "preview": "true",
        },
    )
    assert response.status_code == 200
    assert "Podgląd zmian" in str(response.content, "utf-8")

    # Then confirm the remapping
    response = logged_in_admin_client.post(
        url,
        {
            "jednostka_z": jednostka_domyslna.pk,
            "jednostka_do": jednostka_docelowa.pk,
            "confirm": "true",
        },
    )
    assert response.status_code == 302  # Redirect after success

    # Check that works have been moved
    assert (
        Wydawnictwo_Ciagle_Autor.objects.filter(
            autor=autor, jednostka=jednostka_domyslna
        ).count()
        == 0
    )
    assert (
        Wydawnictwo_Ciagle_Autor.objects.filter(
            autor=autor, jednostka=jednostka_docelowa
        ).count()
        == 1
    )

    assert (
        Wydawnictwo_Zwarte_Autor.objects.filter(
            autor=autor, jednostka=jednostka_domyslna
        ).count()
        == 0
    )
    assert (
        Wydawnictwo_Zwarte_Autor.objects.filter(
            autor=autor, jednostka=jednostka_docelowa
        ).count()
        == 1
    )

    # Check that a log entry was created
    log_entry = PrzemapoaniePracAutora.objects.filter(autor=autor).first()
    assert log_entry is not None
    assert log_entry.jednostka_z == jednostka_domyslna
    assert log_entry.jednostka_do == jednostka_docelowa
    assert log_entry.liczba_prac_ciaglych == 1
    assert log_entry.liczba_prac_zwartych == 1
    assert log_entry.utworzono_przez == admin_user


@pytest.mark.django_db
def test_form_validation_same_units(logged_in_admin_client, autor, jednostka_domyslna):
    """Test that form validation prevents selecting the same unit as source and target"""
    url = reverse(
        "przemapuj_prace_autora:przemapuj_prace", kwargs={"autor_id": autor.pk}
    )

    # Try to preview with same source and target unit
    response = logged_in_admin_client.post(
        url,
        {
            "jednostka_z": jednostka_domyslna.pk,
            "jednostka_do": jednostka_domyslna.pk,
            "preview": "true",
        },
    )

    assert response.status_code == 200
    # The form should have errors
    assert "form" in response.context
    assert response.context["form"].errors
