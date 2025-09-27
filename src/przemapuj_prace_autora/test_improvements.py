import pytest
from django.test import Client
from django.urls import reverse
from model_bakery import baker

from .forms import PrzemapoaniePracAutoraForm

from django.contrib.auth import get_user_model

from bpp.models import (
    Autor,
    Jednostka,
    Uczelnia,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Ciagle_Autor,
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
    return baker.make(Uczelnia, nazwa="Test University", skrot="TU")


@pytest.fixture
def jednostka_domyslna(uczelnia):
    """Create the default unit"""
    return baker.make(
        Jednostka, nazwa="Jednostka Domyślna", skrot="JD", uczelnia=uczelnia
    )


@pytest.fixture
def jednostka_normalna(uczelnia):
    """Create a normal unit"""
    return baker.make(
        Jednostka, nazwa="Jednostka Normalna", skrot="JN", uczelnia=uczelnia
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
def test_jednostka_domyslna_not_in_target_options(
    autor, jednostka_domyslna, jednostka_normalna
):
    """Test that 'Jednostka Domyślna' is not available as target unit"""
    # Create a work for the author in normal unit
    wydawnictwo = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Test Article")
    baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=wydawnictwo,
        autor=autor,
        jednostka=jednostka_normalna,
    )

    form = PrzemapoaniePracAutoraForm(autor=autor)

    # Check that Jednostka Domyślna is NOT in target options
    target_jednostki_names = [j.nazwa for j in form.fields["jednostka_do"].queryset]
    assert "Jednostka Domyślna" not in target_jednostki_names
    assert jednostka_normalna.nazwa in target_jednostki_names


@pytest.mark.django_db
def test_validation_prevents_jednostka_domyslna_as_target(
    autor, jednostka_domyslna, jednostka_normalna
):
    """Test that form validation prevents selecting 'Jednostka Domyślna' as target"""
    # Create a work for the author in normal unit
    wydawnictwo = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Test Article")
    baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=wydawnictwo,
        autor=autor,
        jednostka=jednostka_normalna,
    )

    form = PrzemapoaniePracAutoraForm(
        data={
            "jednostka_z": jednostka_normalna.pk,
            "jednostka_do": jednostka_domyslna.pk,
        },
        autor=autor,
    )

    # Even if someone somehow submits Jednostka Domyślna, it should be invalid
    # Note: Since Jednostka Domyślna is excluded from queryset, Django will raise
    # a validation error saying it's not a valid choice
    assert not form.is_valid()
    # Check either in field errors or non-field errors
    assert "jednostka_do" in form.errors or "__all__" in form.errors


@pytest.mark.django_db
def test_single_unit_is_set_as_default_source(autor, jednostka_normalna):
    """Test that when author has works in only one unit, it's set as default source"""
    # Create a work for the author in only one unit
    wydawnictwo = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Test Article")
    baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=wydawnictwo,
        autor=autor,
        jednostka=jednostka_normalna,
    )

    form = PrzemapoaniePracAutoraForm(autor=autor)

    # The only unit with works should be set as initial source
    assert form.fields["jednostka_z"].initial == jednostka_normalna.pk

    # And the author's current unit should be set as target (if different)
    assert form.fields["jednostka_do"].initial == autor.aktualna_jednostka.pk


@pytest.mark.django_db
def test_jednostka_domyslna_as_default_when_present(
    autor, jednostka_domyslna, jednostka_normalna, jednostka_docelowa
):
    """Test that 'Jednostka Domyślna' is set as default source when author has works there"""
    # Create works in both units
    wydawnictwo1 = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Test Article 1")
    baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=wydawnictwo1,
        autor=autor,
        jednostka=jednostka_domyslna,
    )

    wydawnictwo2 = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Test Article 2")
    baker.make(
        Wydawnictwo_Ciagle_Autor,
        rekord=wydawnictwo2,
        autor=autor,
        jednostka=jednostka_normalna,
    )

    form = PrzemapoaniePracAutoraForm(autor=autor)

    # When author has works in multiple units including Jednostka Domyślna,
    # it should be set as default source
    assert form.fields["jednostka_z"].initial == jednostka_domyslna.pk

    # And the author's current unit should be set as target
    assert form.fields["jednostka_do"].initial == autor.aktualna_jednostka.pk


@pytest.mark.django_db
def test_przemapuj_prace_button_style_class(logged_in_admin_client, autor):
    """Test that the 'Przemapuj prace' button has the correct style class"""
    url = reverse("bpp:browse_autor", kwargs={"slug": autor.slug})
    response = logged_in_admin_client.get(url)

    assert response.status_code == 200
    content = str(response.content, "utf-8")

    # Check that the button has the correct class
    assert 'class="jednostka-remap-button"' in content
    assert "fi-shuffle" in content
