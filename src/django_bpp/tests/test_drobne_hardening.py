"""Testy drobnych wzmocnień: trasy testowe błędów, odmontowane zakładki
admin_tools, nagłówek Content-Security-Policy."""

import pytest
from django.http import HttpResponse
from django.test import RequestFactory
from django.urls import NoReverseMatch, reverse
from model_bakery import baker

from django_bpp.csp import ContentSecurityPolicyMiddleware

# --- /test_500/, /test_exception/, /test_403/: tylko superuser ---


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["/test_403/", "/test_500/", "/test_exception/"])
def test_trasy_testowe_bledow_anonim_na_logowanie(client, url):
    res = client.get(url)
    assert res.status_code == 302
    assert "login" in res["Location"]


@pytest.mark.django_db
@pytest.mark.parametrize("url", ["/test_403/", "/test_500/", "/test_exception/"])
def test_trasy_testowe_bledow_zwykly_user_403(client, url):
    user = baker.make("bpp.BppUser", is_staff=False, is_superuser=False)
    client.force_login(user)
    assert client.get(url).status_code == 403


@pytest.mark.django_db
def test_trasa_test_500_superuser_dostaje_podglad(client, admin_user):
    client.force_login(admin_user)
    # 200 gdy wygenerowano 500.html, 404 gdy nie — w obu przypadkach widok
    # się wykonał (nie 403).
    assert client.get("/test_500/").status_code in (200, 404)


@pytest.mark.django_db
def test_trasa_test_exception_superuser_wykonuje_widok(client, admin_user):
    client.force_login(admin_user)
    with pytest.raises(Exception, match="Celowe"):
        client.get("/test_exception/")


# --- admin_tools: zakładki menu odmontowane, dashboard zostaje ---


@pytest.mark.parametrize(
    "name,kwargs",
    [
        ("admin-tools-menu-add-bookmark", {}),
        ("admin-tools-menu-edit-bookmark", {"id": 1}),
        ("admin-tools-menu-remove-bookmark", {"id": 1}),
    ],
)
def test_admin_tools_zakladki_odmontowane(name, kwargs):
    with pytest.raises(NoReverseMatch):
        reverse(name, kwargs=kwargs)


@pytest.mark.django_db
def test_admin_tools_add_bookmark_404(client, admin_user):
    client.force_login(admin_user)
    assert client.get("/admin_tools/menu/add_bookmark/").status_code == 404


def test_admin_tools_dashboard_preferences_nadal_podpiete():
    url = reverse("admin-tools-dashboard-set-preferences", kwargs={"dashboard_id": "x"})
    assert url.startswith("/admin_tools/dashboard/")


@pytest.mark.django_db
def test_admin_index_renderuje_sie_bez_tras_zakladek(client, admin_user):
    client.force_login(admin_user)
    assert client.get(reverse("admin:index")).status_code == 200


# --- CSP ---


def _odpowiedz(middleware_settings, settings, response=None):
    for k, v in middleware_settings.items():
        setattr(settings, k, v)
    mw = ContentSecurityPolicyMiddleware(
        lambda request: response if response is not None else HttpResponse("ok")
    )
    return mw(RequestFactory().get("/"))


def test_csp_domyslnie_report_only(settings):
    res = _odpowiedz({"BPP_CSP_ENABLED": True, "BPP_CSP_REPORT_ONLY": True}, settings)
    assert "Content-Security-Policy-Report-Only" in res
    assert "Content-Security-Policy" not in res
    polityka = res["Content-Security-Policy-Report-Only"]
    assert "default-src 'self'" in polityka
    assert "object-src 'none'" in polityka


def test_csp_tryb_wymuszajacy(settings):
    res = _odpowiedz({"BPP_CSP_ENABLED": True, "BPP_CSP_REPORT_ONLY": False}, settings)
    assert "Content-Security-Policy" in res
    assert "Content-Security-Policy-Report-Only" not in res


def test_csp_wylaczony(settings):
    res = _odpowiedz({"BPP_CSP_ENABLED": False}, settings)
    assert "Content-Security-Policy" not in res
    assert "Content-Security-Policy-Report-Only" not in res


def test_csp_wlasna_polityka_i_report_uri(settings):
    res = _odpowiedz(
        {
            "BPP_CSP_ENABLED": True,
            "BPP_CSP_REPORT_ONLY": True,
            "BPP_CSP_POLICY": "default-src 'none'",
            "BPP_CSP_REPORT_URI": "https://csp.example.com/r",
        },
        settings,
    )
    assert res["Content-Security-Policy-Report-Only"] == (
        "default-src 'none'; report-uri https://csp.example.com/r"
    )


def test_csp_nie_nadpisuje_istniejacego_naglowka(settings):
    istniejaca = HttpResponse("ok")
    istniejaca["Content-Security-Policy-Report-Only"] = "default-src 'none'"
    res = _odpowiedz(
        {"BPP_CSP_ENABLED": True, "BPP_CSP_REPORT_ONLY": True},
        settings,
        response=istniejaca,
    )
    assert res["Content-Security-Policy-Report-Only"] == "default-src 'none'"


def test_csp_middleware_wpiety_po_security_middleware(settings):
    mw = list(settings.MIDDLEWARE)
    assert "django_bpp.csp.ContentSecurityPolicyMiddleware" in mw
    assert mw.index("django_bpp.csp.ContentSecurityPolicyMiddleware") == (
        mw.index("django.middleware.security.SecurityMiddleware") + 1
    )


def test_csp_domyslnie_wlaczony_w_trybie_report_only():
    from django.conf import settings as dj_settings

    assert dj_settings.BPP_CSP_ENABLED is True
    assert dj_settings.BPP_CSP_REPORT_ONLY is True
