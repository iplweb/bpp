"""Tests for the BPP-specific UczelniaSetupStep.

The generic admin-user step and middleware are tested in the
django-first-run-wizard package itself; this module covers only the
BPP-side glue.
"""

import pytest
from django.test import Client
from django.urls import reverse

from bpp.models import Uczelnia
from bpp_setup_wizard.steps import UczelniaSetupStep


@pytest.fixture(autouse=True)
def enable_first_run_wizard_middleware(settings):
    """Re-enable the first-run wizard middleware for tests in this module.

    `settings/test.py` strips it from MIDDLEWARE globally; we want it
    back for these specific tests of the wizard flow.
    """
    middleware = list(settings.MIDDLEWARE)
    if "first_run_wizard.middleware.FirstRunWizardMiddleware" not in middleware:
        try:
            auth_index = middleware.index(
                "django.contrib.auth.middleware.AuthenticationMiddleware"
            )
            middleware.insert(
                auth_index + 1,
                "first_run_wizard.middleware.FirstRunWizardMiddleware",
            )
        except ValueError:
            middleware.insert(0, "first_run_wizard.middleware.FirstRunWizardMiddleware")
        settings.MIDDLEWARE = middleware


@pytest.mark.django_db
def test_uczelnia_step_is_incomplete_when_no_uczelnia():
    Uczelnia.objects.all().delete()
    assert UczelniaSetupStep().is_complete() is False


@pytest.mark.django_db
def test_uczelnia_step_is_complete_when_uczelnia_exists(uczelnia):
    assert UczelniaSetupStep().is_complete() is True


@pytest.mark.django_db
def test_uczelnia_step_requires_superuser():
    step = UczelniaSetupStep()
    assert step.requires_superuser is True
    assert step.order == 100  # after admin_user


@pytest.mark.django_db
def test_uczelnia_setup_requires_login():
    Uczelnia.objects.all().delete()
    client = Client()
    response = client.get(reverse("first_run_wizard:step", kwargs={"name": "uczelnia"}))
    # WizardStepView checks is_accessible() and redirects anonymous users
    # to '/' (since uczelnia step requires_superuser=True).
    assert response.status_code == 302
    assert response.url == "/"


@pytest.mark.django_db
def test_uczelnia_setup_form_display(admin_user):
    Uczelnia.objects.all().delete()
    client = Client()
    client.force_login(admin_user)

    response = client.get(reverse("first_run_wizard:step", kwargs={"name": "uczelnia"}))

    assert response.status_code == 200
    content = response.content.decode("utf-8")
    assert "Konfiguracja uczelni" in content
    assert "Nazwa uczelni" in content
    assert "Nazwa w dopełniaczu" in content
    assert "Skrót uczelni" in content
    assert "Środowisko PBN" in content
    assert "Używaj wydziałów" in content


@pytest.mark.django_db
def test_uczelnia_setup_creates_uczelnia(admin_user):
    Uczelnia.objects.all().delete()
    client = Client()
    client.force_login(admin_user)

    response = client.post(
        reverse("first_run_wizard:step", kwargs={"name": "uczelnia"}),
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

    assert response.status_code == 302
    assert response.url == "/"

    assert Uczelnia.objects.count() == 1
    uczelnia = Uczelnia.objects.first()
    assert uczelnia.nazwa == "Uniwersytet Testowy"
    assert uczelnia.nazwa_dopelniacz_field == "Uniwersytetu Testowego"
    assert uczelnia.nazwa_dopelniacz() == "Uniwersytetu Testowego"
    assert uczelnia.skrot == "UT"
    assert uczelnia.pbn_api_root == "https://pbn-micro-alpha.opi.org.pl"
    assert uczelnia.pbn_app_name == "test_app"
    assert uczelnia.pbn_app_token == "test_token"
    assert uczelnia.uzywaj_wydzialow is True

    # Auto-set PBN flags
    assert uczelnia.pbn_api_kasuj_przed_wysylka is True
    assert uczelnia.pbn_api_nie_wysylaj_prac_bez_pk is True
    assert uczelnia.pbn_api_afiliacja_zawsze_na_uczelnie is True
    assert uczelnia.pbn_wysylaj_bez_oswiadczen is True
    assert uczelnia.pbn_integracja is True
    assert uczelnia.pbn_aktualizuj_na_biezaco is True


@pytest.mark.django_db
def test_uczelnia_setup_not_accessible_when_exists(admin_user, uczelnia):
    client = Client()
    client.force_login(admin_user)

    response = client.get(reverse("first_run_wizard:step", kwargs={"name": "uczelnia"}))

    # Step is_complete()==True → WizardStepView redirects to '/'.
    assert response.status_code == 302
    assert response.url == "/"


@pytest.mark.django_db
def test_middleware_redirects_logged_in_admin_to_uczelnia_setup(admin_user):
    """End-to-end: admin user exists, no Uczelnia → middleware redirects
    to /setup/step/uczelnia/."""
    Uczelnia.objects.all().delete()
    client = Client()
    client.force_login(admin_user)

    response = client.get("/")
    assert response.status_code == 302
    assert response.url == reverse("first_run_wizard:step", kwargs={"name": "uczelnia"})
