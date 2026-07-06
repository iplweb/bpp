import pytest
from django.test import override_settings
from django.urls import reverse

from django_bpp.external_auth import (
    MICROSOFT_BACKEND,
    OIDC_BACKEND,
    ORCID_BACKEND,
)
from django_bpp.views import SmartPasswordChangeView

pytestmark = pytest.mark.django_db


def test_external_provider_info_microsoft():
    provider, url = SmartPasswordChangeView._external_provider_info(MICROSOFT_BACKEND)
    assert provider == "Microsoft"
    assert url


def test_external_provider_info_orcid():
    provider, url = SmartPasswordChangeView._external_provider_info(ORCID_BACKEND)
    assert provider == "ORCID"
    assert url


@override_settings(OIDC_ACCOUNT_CONSOLE_URL="https://kc.example/realms/uafm/account")
def test_external_provider_info_oidc_uses_account_console_url():
    # Regresja na KeyError → 500: backend OIDC jest w EXTERNAL_AUTH_BACKENDS, ale
    # brakowało go w mapie URL-i, więc dispatch wywalał się na słowniku.
    provider, url = SmartPasswordChangeView._external_provider_info(OIDC_BACKEND)
    assert "Keycloak" in provider
    assert url == "https://kc.example/realms/uafm/account"


def test_external_provider_info_oidc_without_console_url_does_not_crash():
    # Bez skonfigurowanego URL-a konta nadal nie wolno rzucać wyjątku — pusty
    # URL, a szablon po prostu nie pokaże przycisku.
    provider, url = SmartPasswordChangeView._external_provider_info(OIDC_BACKEND)
    assert "Keycloak" in provider
    assert url == ""


def test_oidc_session_does_not_500_on_password_change(client, test_user):
    # Reprodukcja zgłoszenia: użytkownik zalogowany przez Keycloaka wchodzi na
    # /password_change/ i dostawał błąd 500. Teraz ma dostać przyjazną stronę.
    client.force_login(test_user, backend=OIDC_BACKEND)

    response = client.get(reverse("password_change"))

    assert response.status_code == 200
    assert "registration/password_change_external.html" in [
        t.name for t in response.templates
    ]
