import pytest
from django.contrib.auth import get_user_model
from django.test import Client
from django.urls import reverse

from bpp.models import Uczelnia

BppUser = get_user_model()


@pytest.fixture(autouse=True)
def enable_setup_wizard_middleware(settings):
    """Enable SetupWizardMiddleware for all tests in this module."""
    middleware = list(settings.MIDDLEWARE)
    if "bpp_setup_wizard.middleware.SetupWizardMiddleware" not in middleware:
        # Add the middleware after AuthenticationMiddleware to ensure user is available
        try:
            auth_index = middleware.index(
                "django.contrib.auth.middleware.AuthenticationMiddleware"
            )
            middleware.insert(
                auth_index + 1, "bpp_setup_wizard.middleware.SetupWizardMiddleware"
            )
        except ValueError:
            # If AuthenticationMiddleware is not found, add at the beginning
            middleware.insert(0, "bpp_setup_wizard.middleware.SetupWizardMiddleware")
        settings.MIDDLEWARE = middleware


@pytest.mark.django_db
def test_setup_wizard_redirect_when_no_users():
    """Test that the middleware redirects to setup when no users exist."""
    client = Client()

    # Verify no users exist
    assert BppUser.objects.count() == 0

    # Try to access the home page
    response = client.get("/")

    # Should redirect to setup wizard
    assert response.status_code == 302
    assert response.url == reverse("bpp_setup_wizard:setup")


@pytest.mark.django_db
def test_setup_wizard_form_display():
    """Test that the setup wizard form is displayed correctly."""
    client = Client()

    # Verify no users exist
    assert BppUser.objects.count() == 0

    # Access the setup wizard page
    response = client.get(reverse("bpp_setup_wizard:setup"))

    # Should display the form
    assert response.status_code == 200
    assert "Kreator konfiguracji BPP" in response.content.decode("utf-8")
    assert "Nazwa użytkownika" in response.content.decode("utf-8")
    assert "Adres email" in response.content.decode("utf-8")
    assert "Hasło" in response.content.decode("utf-8")


@pytest.mark.django_db
def test_setup_wizard_create_admin_user():
    """Test that the setup wizard creates an admin user correctly."""
    client = Client()

    # Verify no users exist
    assert BppUser.objects.count() == 0

    # Submit the form
    response = client.post(
        reverse("bpp_setup_wizard:setup"),
        {
            "username": "testadmin",
            "email": "admin@test.com",
            "password1": "TestPassword123!",
            "password2": "TestPassword123!",
        },
    )

    # Should redirect to main page after successful creation
    assert response.status_code == 302
    assert response.url == "/"

    # Verify the user was created
    assert BppUser.objects.count() == 1
    user = BppUser.objects.first()
    assert user.username == "testadmin"
    assert user.email == "admin@test.com"
    assert user.is_staff is True
    assert user.is_superuser is True
    assert user.is_active is True


@pytest.mark.django_db
def test_setup_wizard_not_accessible_when_users_exist(normal_django_user):
    """Test that the setup wizard is not accessible when users already exist."""
    client = Client()

    # Verify users exist
    assert BppUser.objects.count() > 0

    # Try to access the setup wizard
    response = client.get(reverse("bpp_setup_wizard:setup"))

    # Should redirect away from setup
    assert response.status_code == 302
    assert response.url == "/"


@pytest.mark.django_db
def test_setup_wizard_status_view_needs_setup():
    """Test that the status view correctly shows setup is needed."""
    client = Client()

    # Verify no users exist
    assert BppUser.objects.count() == 0

    # Access the status page
    response = client.get(reverse("bpp_setup_wizard:status"))

    # Should show setup is needed
    assert response.status_code == 200
    assert "Wymagana konfiguracja" in response.content.decode("utf-8")
    assert "Uruchom kreator konfiguracji" in response.content.decode("utf-8")


@pytest.mark.django_db
def test_setup_wizard_status_view_already_configured(normal_django_user):
    """Test that the status view correctly shows system is configured."""
    client = Client()

    # Verify users exist
    user_count = BppUser.objects.count()
    assert user_count > 0

    # Access the status page
    response = client.get(reverse("bpp_setup_wizard:status"))

    # Should show system is configured
    assert response.status_code == 200
    assert "System skonfigurowany" in response.content.decode("utf-8")
    assert str(user_count) in response.content.decode("utf-8")


@pytest.mark.django_db
def test_uczelnia_setup_requires_login():
    """Test that Uczelnia setup requires authentication."""
    client = Client()

    # Clean up any existing Uczelnia
    Uczelnia.objects.all().delete()

    # Try to access without login
    response = client.get(reverse("bpp_setup_wizard:uczelnia_setup"))

    # Should redirect to login
    assert response.status_code == 302
    assert "/accounts/login/" in response.url


@pytest.mark.django_db
def test_uczelnia_setup_requires_superuser(normal_django_user):
    """Test that Uczelnia setup requires superuser privileges."""
    client = Client()

    # Clean up any existing Uczelnia
    Uczelnia.objects.all().delete()

    # Login as normal user
    client.force_login(normal_django_user)

    # Try to access Uczelnia setup
    response = client.get(reverse("bpp_setup_wizard:uczelnia_setup"))

    # Should redirect away
    assert response.status_code == 302
    assert response.url == "/"


@pytest.mark.django_db
def test_uczelnia_setup_form_display(admin_user):
    """Test that the Uczelnia setup form is displayed correctly."""
    client = Client()

    # Clean up any existing Uczelnia
    Uczelnia.objects.all().delete()

    # Login as admin
    client.force_login(admin_user)

    # Access the Uczelnia setup page
    response = client.get(reverse("bpp_setup_wizard:uczelnia_setup"))

    # Should display the form
    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Konfiguracja uczelni" in content
    assert "Nazwa uczelni" in content
    assert "Nazwa w dopełniaczu" in content
    assert "Skrót uczelni" in content
    assert "Środowisko PBN" in content
    assert "Używaj wydziałów" in content


@pytest.mark.django_db
def test_uczelnia_setup_create_uczelnia(admin_user):
    """Test that the Uczelnia setup creates a university configuration correctly."""
    client = Client()

    # Clean up any existing Uczelnia
    Uczelnia.objects.all().delete()

    # Login as admin
    client.force_login(admin_user)

    # Submit the form
    response = client.post(
        reverse("bpp_setup_wizard:uczelnia_setup"),
        {
            "nazwa": "Uniwersytet Testowy",
            "nazwa_dopelniacz_field": "Uniwersytetu Testowego",
            "skrot": "UT",
            "pbn_api_root": "https://pbn-micro-alpha.opi.org.pl",
            "pbn_app_name": "test_app",
            "pbn_app_token": "test_token",
            "uzywaj_wydzialow": True,
        },
    )

    # Should redirect to main page after successful creation
    assert response.status_code == 302
    assert response.url == "/"

    # Verify the Uczelnia was created with correct data
    assert Uczelnia.objects.count() == 1
    uczelnia = Uczelnia.objects.first()
    assert uczelnia.nazwa == "Uniwersytet Testowy"
    assert uczelnia.nazwa_dopelniacz_field == "Uniwersytetu Testowego"
    assert (
        uczelnia.nazwa_dopelniacz() == "Uniwersytetu Testowego"
    )  # Method should return the field value
    assert uczelnia.skrot == "UT"
    assert uczelnia.pbn_api_root == "https://pbn-micro-alpha.opi.org.pl"
    assert uczelnia.pbn_app_name == "test_app"
    assert uczelnia.pbn_app_token == "test_token"
    assert uczelnia.uzywaj_wydzialow is True

    # Verify the automatically set fields
    assert uczelnia.pbn_api_kasuj_przed_wysylka is True
    assert uczelnia.pbn_api_nie_wysylaj_prac_bez_pk is True
    assert uczelnia.pbn_api_afiliacja_zawsze_na_uczelnie is True
    assert uczelnia.pbn_wysylaj_bez_oswiadczen is True
    assert uczelnia.pbn_integracja is True
    assert uczelnia.pbn_aktualizuj_na_biezaco is True


@pytest.mark.django_db
def test_uczelnia_setup_not_accessible_when_exists(admin_user, uczelnia):
    """Test that Uczelnia setup is not accessible when Uczelnia already exists."""
    client = Client()

    # Login as admin
    client.force_login(admin_user)

    # Try to access the Uczelnia setup
    response = client.get(reverse("bpp_setup_wizard:uczelnia_setup"))

    # Should redirect away from setup
    assert response.status_code == 302
    assert response.url == "/"


@pytest.mark.django_db
def test_middleware_redirects_to_uczelnia_setup_after_user_setup():
    """Test that middleware redirects to Uczelnia setup after user is created."""
    client = Client()

    # Clean up
    BppUser.objects.all().delete()
    Uczelnia.objects.all().delete()

    # First create an admin user
    response = client.post(
        reverse("bpp_setup_wizard:setup"),
        {
            "username": "testadmin",
            "email": "admin@test.com",
            "password1": "TestPassword123!",
            "password2": "TestPassword123!",
        },
    )

    # Should redirect to main page
    assert response.status_code == 302
    assert response.url == "/"

    # Login as the admin user we just created
    admin = BppUser.objects.get(username="testadmin")
    client.force_login(admin)

    # Now trying to access main page should redirect to Uczelnia setup
    # (since user is logged in as superuser and no Uczelnia exists)
    response = client.get("/")
    assert response.status_code == 302
    assert response.url == reverse("bpp_setup_wizard:uczelnia_setup")
