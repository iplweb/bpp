import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Autor, Jednostka, Uczelnia

User = get_user_model()


@pytest.fixture
def admin_user_with_group(db):
    """Create an admin user with wprowadzanie danych group"""
    from django.contrib.auth.models import Group

    user = User.objects.create_user(
        username="testadmin", password="testpass", is_staff=True, is_superuser=True
    )
    group, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(group)
    return user


@pytest.fixture
def logged_in_admin_client(admin_user_with_group):
    """Create a logged in admin client"""
    client = Client()
    client.login(username="testadmin", password="testpass")
    return client


@pytest.fixture
def uczelnia(db):
    """Create a test university"""
    return baker.make(Uczelnia, nazwa="Test University", skrot="TU")


@pytest.fixture
def jednostka(uczelnia):
    """Create a test unit"""
    return baker.make(Jednostka, nazwa="Test Unit", skrot="TU", uczelnia=uczelnia)


@pytest.fixture
def autor(jednostka):
    """Create a test author"""
    return baker.make(
        Autor, imiona="Jan", nazwisko="Kowalski", aktualna_jednostka=jednostka
    )


@pytest.mark.django_db
def test_buttons_are_displayed_horizontally(logged_in_admin_client, autor):
    """Test that both buttons are displayed in a single horizontal line"""
    url = reverse("bpp:browse_autor", kwargs={"slug": autor.slug})
    response = logged_in_admin_client.get(url)

    assert response.status_code == 200
    content = str(response.content, "utf-8")

    # Check that both buttons exist
    assert "Przemapuj prace" in content
    assert "Otwórz do edycji" in content

    # Check that they're in a flex container (class with display:flex in SCSS)
    assert "autor-page__actions" in content

    # Check that both have correct classes
    assert "jednostka-remap-button" in content
    assert "jednostka-edit-button" in content

    # Verify the buttons are not wrapped in separate divs that would stack them
    # The buttons should be siblings within the same container
    import re

    # Look for the pattern where both buttons are in the same container
    pattern = (
        r"<div[^>]*autor-page__actions[^>]*>.*?"
        r"jednostka-remap-button.*?jednostka-edit-button.*?</div>"
    )
    assert re.search(pattern, content.replace("\n", " "), re.DOTALL)


@pytest.mark.django_db
def test_przemapuj_button_hidden_for_anonymous(autor):
    """Test that the Przemapuj prace button is hidden for anonymous users"""
    client = Client()
    url = reverse("bpp:browse_autor", kwargs={"slug": autor.slug})
    response = client.get(url)

    assert response.status_code == 200
    content = str(response.content, "utf-8")

    # Przemapuj prace should not be visible
    assert "Przemapuj prace" not in content

    # But the container should still be there (empty or with just edit button)
    assert "hide-for-print" in content


@pytest.mark.django_db
def test_both_buttons_for_admin_user(logged_in_admin_client, autor):
    """Test that admin users see both buttons"""
    url = reverse("bpp:browse_autor", kwargs={"slug": autor.slug})
    response = logged_in_admin_client.get(url)

    assert response.status_code == 200
    content = str(response.content, "utf-8")

    # Both buttons should be present (check href attributes)
    assert f"/przemapuj_prace_autora/autor/{autor.pk}/" in content
    assert f"/admin/bpp/autor/{autor.pk}/change/" in content

    # Check the icons are present
    assert "fi-shuffle" in content
    assert "fi-page-edit" in content
