"""Testy InstitutionalLoginView — per-uczelnia dyspozytora logowania.

Precedencja: OIDC (gateowany po skrócie) > Microsoft (globalny) > formularz BPP.
Reverse'y prowadzą do tras, których w ustawieniach testowych nie ma (OIDC/
Microsoft niezainstalowane), więc mockujemy `reverse` i `apps.is_installed`.
"""

from django.apps import apps
from django.http import HttpResponse

from django_bpp.views import InstitutionalLoginView


def test_dispatch_oidc_redirect_z_next(rf, mocker):
    mocker.patch("oidc_integration.access.oidc_enabled_for_request", return_value=True)
    mocker.patch("django_bpp.views.reverse", return_value="/oidc/authenticate/")

    resp = InstitutionalLoginView.as_view()(rf.get("/accounts/login/?next=/foo/"))

    assert resp.status_code == 302
    assert resp.url == "/oidc/authenticate/?next=%2Ffoo%2F"


def test_dispatch_microsoft_gdy_oidc_nie_dotyczy(rf, mocker):
    mocker.patch("oidc_integration.access.oidc_enabled_for_request", return_value=False)
    mocker.patch.object(apps, "is_installed", return_value=True)  # microsoft_auth
    mocker.patch("django_bpp.views.reverse", return_value="/microsoft/redirect/")

    resp = InstitutionalLoginView.as_view()(rf.get("/accounts/login/"))

    assert resp.status_code == 302
    assert resp.url == "/microsoft/redirect/"


def test_dispatch_formularz_bpp_gdy_brak_instytucjonalnego(rf, mocker):
    mocker.patch("oidc_integration.access.oidc_enabled_for_request", return_value=False)
    mocker.patch.object(apps, "is_installed", return_value=False)
    sentinel = HttpResponse("LOCAL")
    mocker.patch(
        "django_bpp.views.HTMXAwareLoginView.as_view",
        return_value=lambda *a, **k: sentinel,
    )

    resp = InstitutionalLoginView.as_view()(rf.get("/accounts/login/"))

    assert resp is sentinel
