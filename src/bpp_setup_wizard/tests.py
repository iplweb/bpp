"""Tests for the BPP-specific wizard steps (Uczelnia + PBN).

The generic admin-user step and middleware are tested in the
django-first-run-wizard package itself; this module covers only the
BPP-side glue.
"""

import pytest
from django.contrib.auth import get_user_model
from django.template.loader import get_template
from django.test import Client
from django.urls import reverse

from bpp.models import Uczelnia
from bpp_setup_wizard.steps import UczelniaSetupStep

# Test password used by HTTP tests that submit AdminUserCreationForm.
# Must satisfy Django's default AUTH_PASSWORD_VALIDATORS (length ≥ 8,
# not similar to username, not in common-password list, not all numeric).
# Not a real credential.
_TEST_PASSWORD = "wizard-test-pass-min8"  # pragma: allowlist secret  # noqa: S105


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
    assert "Używaj wydziałów" in content
    # FD#499: krok „Dane uczelni" nie zawiera pól PBN.
    assert "Środowisko PBN" not in content
    assert 'name="pbn_app_token"' not in content
    assert "Krok 2 z 3" in content


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
            "uzywaj_wydzialow": True,
        },
    )

    # FD#499: po danych uczelni kreator prowadzi do kroku 3 (PBN).
    assert response.status_code == 302
    assert response.url == reverse("bpp_setup_wizard:pbn")

    assert Uczelnia.objects.count() == 1
    uczelnia = Uczelnia.objects.first()
    assert uczelnia.nazwa == "Uniwersytet Testowy"
    assert uczelnia.nazwa_dopelniacz_field == "Uniwersytetu Testowego"
    assert uczelnia.nazwa_dopelniacz() == "Uniwersytetu Testowego"
    assert uczelnia.skrot == "UT"
    assert uczelnia.pbn_app_name == ""
    assert uczelnia.pbn_app_token == ""
    assert uczelnia.uzywaj_wydzialow is True

    # Verify the automatically set fields
    assert uczelnia.pbn_kasuj_dyscypliny_selektywnie is True
    assert uczelnia.pbn_api_nie_wysylaj_prac_bez_pk is True
    assert uczelnia.pbn_api_afiliacja_zawsze_na_uczelnie is True
    assert uczelnia.pbn_wysylaj_bez_oswiadczen is True
    assert uczelnia.pbn_integracja is True
    assert uczelnia.pbn_aktualizuj_na_biezaco is True


@pytest.mark.django_db
def test_uczelnia_setup_not_accessible_when_exists(
    admin_user, uczelnia, first_run_wizard_state
):
    client = Client()
    client.force_login(admin_user)

    response = client.get(reverse("first_run_wizard:step", kwargs={"name": "uczelnia"}))

    # Admin + uczelnia both exist → every step is complete → the wizard is
    # done. With django-first-run-wizard>=0.2.0 the middleware records
    # completion (on construction) and the /setup/ views return 404 — setup
    # is closed for good; deleting the uczelnia no longer re-opens it.
    # ``first_run_wizard_state`` gwarantuje wiersz-singleton stanu (pk=1),
    # normalnie z migracji, a wymiatany przez transakcyjnego sąsiada na CI —
    # bez niego middleware nie backfilluje completed_at i widok zwraca 302.
    assert response.status_code == 404


@pytest.mark.django_db
def test_admin_user_template_loaded_from_bpp_override():
    """INSTALLED_APPS puts bpp_setup_wizard before first_run_wizard so that
    BPP's own first_run_wizard/admin_user.html (BPP-styled, extends bare.html)
    wins over the package's vendor-neutral default. Regression guard for
    accidental reordering."""
    t = get_template("first_run_wizard/admin_user.html")
    assert "bpp_setup_wizard" in t.origin.name, (
        f"loaded from {t.origin.name!r} — expected BPP override "
        f"in src/bpp_setup_wizard/templates/first_run_wizard/"
    )


@pytest.mark.django_db
def test_admin_user_page_is_bpp_branded_and_hides_skip_link():
    """The first-wizard page renders with the BPP wrapper class and the
    accessibility skip-link from bare.html is suppressed (block override)."""
    get_user_model().objects.all().delete()
    response = Client().get(
        reverse("first_run_wizard:step", kwargs={"name": "admin_user"})
    )
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "bpp-setup-wizard" in body, "expected BPP-styled wrapper class"
    assert "Krok 1 z 3" in body
    assert "Przejdź do głównej zawartości" not in body, (
        "skip-link from bare.html should be suppressed on wizard pages "
        "(empty {% block skip_link %}{% endblock %} override)"
    )


@pytest.mark.django_db
def test_uczelnia_setup_page_hides_skip_link(admin_user):
    """Same skip-link suppression for the BPP-specific Uczelnia step."""
    Uczelnia.objects.all().delete()
    client = Client()
    client.force_login(admin_user)
    response = client.get(reverse("first_run_wizard:step", kwargs={"name": "uczelnia"}))
    assert response.status_code == 200
    assert "Przejdź do głównej zawartości" not in response.content.decode("utf-8")


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


@pytest.mark.django_db
def test_admin_user_post_via_bpp_override_creates_superuser():
    """POST na admin_user step gdy renderuje się BPP override.

    Pakiet testuje POST swojego vendor-neutral template-u. Tu sprawdzamy
    że BPP-styled override nie zepsuł HTML form attrs (`name=`, csrf,
    submit button) — POST faktycznie wpływa do AdminUserCreationForm
    z pakietu i tworzy superusera.
    """
    User = get_user_model()
    User.objects.all().delete()
    Uczelnia.objects.all().delete()

    client = Client()
    url = reverse("first_run_wizard:step", kwargs={"name": "admin_user"})
    response = client.post(
        url,
        {
            "username": "bppadmin",
            "email": "admin@bpp.test",
            "password1": _TEST_PASSWORD,
            "password2": _TEST_PASSWORD,
        },
    )

    assert response.status_code == 302, response.content.decode("utf-8")[:500]
    assert response.url == "/"

    assert User.objects.count() == 1
    user = User.objects.get(username="bppadmin")
    assert user.email == "admin@bpp.test"
    assert user.is_staff is True
    assert user.is_superuser is True
    assert user.is_active is True
    assert user.check_password(_TEST_PASSWORD)


@pytest.mark.django_db
def test_full_happy_path_empty_db_to_live_site():
    """E2E na pustej bazie: anonimowy GET / → admin_user form → POST →
    middleware → uczelnia form → POST → krok PBN → „uzupełnię później" →
    site live (brak redirectu setup).

    Jeden Django test Client utrzymuje session przez całą ścieżkę,
    weryfikujemy że wszystkie redirecty i obie strony BPP-styled formularzy
    łączą się w spójny flow.
    """
    User = get_user_model()
    User.objects.all().delete()
    Uczelnia.objects.all().delete()

    client = Client()
    admin_url = reverse("first_run_wizard:step", kwargs={"name": "admin_user"})
    uczelnia_url = reverse("first_run_wizard:step", kwargs={"name": "uczelnia"})

    # 1) Pusta DB → / przekierowuje do admin_user (anon, ale admin step
    # nie requires_superuser, więc accessible).
    response = client.get("/")
    assert response.status_code == 302
    assert response.url == admin_url

    # 2) GET admin_user renderuje BPP-styled formularz.
    response = client.get(admin_url)
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "bpp-setup-wizard" in body
    assert 'name="username"' in body
    assert 'name="password1"' in body

    # 3) POST admin_user → tworzy admina + auto-login + redirect na /.
    response = client.post(
        admin_url,
        {
            "username": "e2eadmin",
            "email": "e2e@bpp.test",
            "password1": _TEST_PASSWORD,
            "password2": _TEST_PASSWORD,
        },
    )
    assert response.status_code == 302
    assert response.url == "/"
    assert User.objects.filter(username="e2eadmin", is_superuser=True).exists()

    # 4) Po stworzeniu admina + automatycznym loginie, GET / przekierowuje
    # do uczelnia (admin jest superuser, więc ma access do tego stepu).
    response = client.get("/")
    assert response.status_code == 302
    assert response.url == uczelnia_url

    # 5) GET uczelnia renderuje BPP-styled formularz.
    response = client.get(uczelnia_url)
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Konfiguracja uczelni" in body
    assert 'name="nazwa"' in body
    assert 'name="pbn_api_root"' not in body

    # 6) POST uczelnia → tworzy Uczelnia z PBN flags + redirect na krok PBN.
    response = client.post(
        uczelnia_url,
        {
            "nazwa": "Uniwersytet E2E",
            "nazwa_dopelniacz_field": "Uniwersytetu E2E",
            "skrot": "UE2E",
            "uzywaj_wydzialow": True,
        },
    )
    assert response.status_code == 302
    assert response.url == reverse("bpp_setup_wizard:pbn")
    uczelnia = Uczelnia.objects.get()
    assert uczelnia.nazwa == "Uniwersytet E2E"
    assert uczelnia.pbn_integracja is True

    # 7) Krok 3 (PBN) zaczyna się od pytania; „uzupełnię później" → pomiń.
    response = client.get(response.url)
    assert response.status_code == 200
    assert "Krok 3 z 3" in response.content.decode("utf-8")
    response = client.post(_pbn_url("pozniej"), {"akcja": "pomin"})
    assert response.status_code == 302
    assert response.url == "/"

    # 8) GET / nie przekierowuje już do setup — site live. Może być 200 albo
    # inny redirect zależnie od głównej routy BPP, ale NIE może być redirect
    # do /setup/ (wszystkie kroki ukończone).
    _assert_site_live(client)


# --- FD#499: krok 3 „Integracja z PBN" -------------------------------------


PBN_TESTOWY = "https://pbn-micro-alpha.opi.org.pl"


def _pbn_url(odpowiedz=None):
    url = reverse("bpp_setup_wizard:pbn")
    if odpowiedz:
        url += f"?odpowiedz={odpowiedz}"
    return url


def _assert_site_live(client):
    response = client.get("/")
    if response.status_code in (301, 302):
        assert "/setup/" not in response.url, (
            f"unexpected redirect to setup wizard after all steps: {response.url}"
        )


@pytest.fixture
def po_kroku_uczelni(request, admin_user, first_run_wizard_state):
    """Stan po kroku 2: admin + uczelnia istnieją, kreator jeszcze otwarty.

    Middleware kreatora powstaje przy pierwszym requeście klienta; gdyby
    zbudował się już przy istniejącej uczelni, ścieżka naprawcza od razu
    stemplowałaby ``completed_at``. W realnym przebiegu worker startuje
    przed konfiguracją — odtwarzamy to: middleware ładujemy bez uczelni,
    dopiero potem ją tworzymy.
    """
    from first_run_wizard.models import FirstRunWizardState

    Uczelnia.objects.all().delete()
    FirstRunWizardState.objects.filter(pk=1).update(completed_at=None)
    client = Client()
    client.force_login(admin_user)
    client.handler.load_middleware()
    request.getfixturevalue("uczelnia")
    return client


@pytest.mark.django_db
def test_pbn_step_zaczyna_sie_od_pytania_bez_formularza(po_kroku_uczelni):
    response = po_kroku_uczelni.get(_pbn_url())
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert "Krok 3 z 3" in body
    assert "Czy masz już nazwę i token aplikacji z PBN?" in body
    assert "Tak, mam oba" in body
    assert "Jeszcze nie, uzupełnię to później" in body
    assert "Nie wiem, o co chodzi" in body
    assert 'name="pbn_app_token"' not in body


@pytest.mark.django_db
def test_pbn_step_tak_pokazuje_formularz(po_kroku_uczelni):
    response = po_kroku_uczelni.get(_pbn_url("tak"))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert 'name="pbn_api_root"' in body
    assert 'name="pbn_app_name"' in body
    assert 'name="pbn_app_token"' in body


@pytest.mark.django_db
def test_pbn_step_tak_zapisuje_dane_pbn(po_kroku_uczelni, uczelnia):
    response = po_kroku_uczelni.post(
        _pbn_url("tak"),
        {
            "akcja": "zapisz",
            "pbn_api_root": PBN_TESTOWY,
            "pbn_app_name": "test_app",
            "pbn_app_token": "test_token",
        },
    )
    assert response.status_code == 302
    assert response.url == "/"

    uczelnia.refresh_from_db()
    assert uczelnia.pbn_api_root == PBN_TESTOWY
    assert uczelnia.pbn_app_name == "test_app"
    assert uczelnia.pbn_app_token == "test_token"
    _assert_site_live(po_kroku_uczelni)


@pytest.mark.django_db
def test_pbn_step_tak_wymaga_nazwy_i_tokenu(po_kroku_uczelni, uczelnia):
    response = po_kroku_uczelni.post(
        _pbn_url("tak"),
        {"akcja": "zapisz", "pbn_api_root": PBN_TESTOWY},
    )
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert 'name="pbn_app_token"' in body
    uczelnia.refresh_from_db()
    assert uczelnia.pbn_app_name == ""


@pytest.mark.django_db
def test_pbn_step_pozniej_wskazuje_gdzie_uzupelnic(po_kroku_uczelni):
    response = po_kroku_uczelni.get(_pbn_url("pozniej"))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert 'name="pbn_app_token"' not in body
    assert "Administracja → Uczelnia" in body
    assert "uzyskanie-integracji-z-api-pbn" in body


@pytest.mark.django_db
def test_pbn_step_nie_wiem_wyjasnia_pbn(po_kroku_uczelni):
    response = po_kroku_uczelni.get(_pbn_url("nie-wiem"))
    assert response.status_code == 200
    body = response.content.decode("utf-8")
    assert 'name="pbn_app_token"' not in body
    assert "Polska Bibliografia Naukowa" in body
    assert "administrator instytucji w PBN" in body
    assert "uzyskanie-integracji-z-api-pbn" in body
    assert "Administracja → Uczelnia" in body
    assert "Rozumiem, pomiń na razie" in body


@pytest.mark.django_db
@pytest.mark.parametrize("odpowiedz", ["pozniej", "nie-wiem"])
def test_pbn_step_pominiecie_konczy_kreator_i_nie_wraca(
    po_kroku_uczelni, uczelnia, odpowiedz
):
    from first_run_wizard.models import FirstRunWizardState

    response = po_kroku_uczelni.post(_pbn_url(odpowiedz), {"akcja": "pomin"})
    assert response.status_code == 302
    assert response.url == "/"

    uczelnia.refresh_from_db()
    assert uczelnia.pbn_app_name == ""
    # Świadome pominięcie jest zapamiętane: kreator zamknięty na dobre,
    # krok PBN nie wraca.
    assert FirstRunWizardState.is_completed()
    _assert_site_live(po_kroku_uczelni)
    assert po_kroku_uczelni.get(_pbn_url()).status_code == 404


@pytest.mark.django_db
def test_pbn_step_wymaga_superusera(po_kroku_uczelni):
    po_kroku_uczelni.logout()
    response = po_kroku_uczelni.get(_pbn_url())
    assert response.status_code == 302
    assert response.url == "/"


@pytest.mark.django_db
def test_pbn_step_bez_uczelni_odsyla_do_kreatora(admin_user):
    Uczelnia.objects.all().delete()
    client = Client()
    client.force_login(admin_user)
    response = client.get(_pbn_url())
    assert response.status_code == 302
    assert response.url == "/"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "path",
    [
        "/admin-dashboard/recent-logins/",
        "/admin-dashboard/weekday-stats/",
    ],
)
def test_middleware_does_not_redirect_admin_dashboard_widgets(admin_user, path):
    """#873: widgety HTMX dashboardu admina (``/admin-dashboard/``) wołane
    z ``/admin/`` przed dokończeniem kreatora nie mogą dostać 302 na krok
    „Konfiguracja uczelni" — HTMX wstawiłby całą stronę kreatora w kafelek."""
    Uczelnia.objects.all().delete()
    client = Client()
    client.force_login(admin_user)

    response = client.get(path, HTTP_HX_REQUEST="true")
    assert response.status_code == 200
    assert "Konfiguracja uczelni" not in response.content.decode("utf-8")
