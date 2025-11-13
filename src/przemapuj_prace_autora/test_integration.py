import pytest
from cacheops import invalidate_all
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import Client
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor, Jednostka, Uczelnia

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
    # Clear any existing universities to ensure get_default() returns our test university
    Uczelnia.objects.all().delete()
    u = baker.make(Uczelnia, nazwa="Test University", skrot="TU")
    # Invalidate all caches so context processor returns the new uczelnia
    cache.delete(b"bpp_uczelnia")
    invalidate_all()
    return u


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
def test_przemapuj_prace_button_appears_on_autor_page(logged_in_admin_client, autor):
    """Test that the 'Przemapuj prace' button appears on the author browse page for logged in users"""
    url = reverse("bpp:browse_autor", kwargs={"slug": autor.slug})
    response = logged_in_admin_client.get(url)

    assert response.status_code == 200
    content = str(response.content, "utf-8")

    # Check that the button is present
    assert "Przemapuj prace" in content
    assert f'href="/przemapuj_prace_autora/autor/{autor.pk}/"' in content
    assert "fi-shuffle" in content  # Check for the icon


@pytest.mark.django_db
def test_przemapuj_prace_button_not_shown_for_anonymous(autor):
    """Test that the 'Przemapuj prace' button does not appear for anonymous users"""
    client = Client()
    url = reverse("bpp:browse_autor", kwargs={"slug": autor.slug})
    response = client.get(url)

    assert response.status_code == 200
    content = str(response.content, "utf-8")

    # Check that the button is not present
    assert "Przemapuj prace" not in content


@pytest.mark.django_db
def test_breadcrumbs_on_wybierz_autora_page(logged_in_admin_client, uczelnia):
    """Test that breadcrumbs appear on the author selection page"""
    url = reverse("przemapuj_prace_autora:wybierz_autora")
    response = logged_in_admin_client.get(url)

    assert response.status_code == 200
    content = str(response.content, "utf-8")

    # Check for breadcrumbs
    assert "breadcrumbs" in content
    assert uczelnia.skrot in content
    assert "Przemapowanie prac autora" in content


@pytest.mark.django_db
def test_breadcrumbs_on_przemapuj_prace_page(logged_in_admin_client, autor, uczelnia):
    """Test that breadcrumbs appear on the remapping page"""
    url = reverse(
        "przemapuj_prace_autora:przemapuj_prace", kwargs={"autor_id": autor.pk}
    )
    response = logged_in_admin_client.get(url)

    assert response.status_code == 200
    content = str(response.content, "utf-8")

    # Check for breadcrumbs
    assert "breadcrumbs" in content
    assert uczelnia.skrot in content
    assert "Przemapowanie prac autora" in content
    assert str(autor) in content
    # Check that the link back to wybierz_autora exists
    assert 'href="/przemapuj_prace_autora/"' in content
