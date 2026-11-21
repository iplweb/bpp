"""HTMX requests of anonymous users must navigate to the login page as a whole.

Without ``HtmxLoginRedirectMiddleware`` HTMX follows the login redirect and
swaps the login form into the fragment it was loading (e.g. the admin filter
panel).
"""

from urllib.parse import parse_qs, urlsplit

import pytest
from django.urls import reverse

from django_bpp.middleware import login_paths

ADMIN_CHANGELIST = "/admin/bpp/autor/"
PAGE = "/admin/bpp/autor/?nazwisko=Kowalski"


def htmx(client, url, current_url="http://testserver" + PAGE, **extra):
    headers = {"HX-Request": "true"}
    if current_url is not None:
        headers["HX-Current-URL"] = current_url
    return client.get(url, headers=headers, **extra)


def split_hx_redirect(response):
    assert response.status_code == 200
    assert response.content == b""
    assert "Location" not in response
    parts = urlsplit(response["HX-Redirect"])
    return parts.path, parse_qs(parts.query)


@pytest.mark.django_db
def test_htmx_admin_changelist_anonymous_hx_redirect_to_admin_login(client):
    res = htmx(client, ADMIN_CHANGELIST)

    path, query = split_hx_redirect(res)
    assert path == reverse("admin:login")
    assert query == {"next": [PAGE]}


@pytest.mark.django_db
def test_htmx_login_required_view_anonymous_hx_redirect_to_login_url(client):
    # TokenRedirectPage uses LoginRequiredMixin -> redirect to LOGIN_URL.
    res = htmx(client, reverse("pbn_api:authorize"), current_url="/raporty/?a=1")

    path, query = split_hx_redirect(res)
    assert path == reverse("login_form")
    assert query == {"next": ["/raporty/?a=1"]}


@pytest.mark.django_db
def test_htmx_permission_denied_anonymous_hx_redirect_to_login(client):
    # ZapytanieView: LoginRequiredMixin + raise_exception=True -> 403 for
    # anonymous users instead of a login redirect.
    assert client.get(reverse("bpp:zapytanie")).status_code == 403

    res = htmx(client, reverse("bpp:zapytanie"))

    path, query = split_hx_redirect(res)
    assert path == reverse("login_form")
    assert query == {"next": [PAGE]}


@pytest.mark.django_db
def test_htmx_permission_denied_logged_in_user_keeps_403(client, normal_django_user):
    client.force_login(normal_django_user)

    res = htmx(client, reverse("bpp:zapytanie"))

    assert res.status_code == 403
    assert "HX-Redirect" not in res


@pytest.mark.django_db
def test_htmx_get_of_login_page_itself_hx_redirect(client):
    res = htmx(client, reverse("admin:login") + "?next=/admin/bpp/autor/")

    path, query = split_hx_redirect(res)
    assert path == reverse("admin:login")
    assert query == {"next": [PAGE]}


@pytest.mark.django_db
def test_non_htmx_request_unchanged(client):
    res = client.get(ADMIN_CHANGELIST)

    assert res.status_code == 302
    assert urlsplit(res["Location"]).path == reverse("admin:login")
    assert "HX-Redirect" not in res


@pytest.mark.django_db
def test_htmx_authenticated_request_unchanged(admin_client):
    res = htmx(admin_client, ADMIN_CHANGELIST)

    assert res.status_code == 200
    assert "HX-Redirect" not in res
    assert b"<" in res.content


@pytest.mark.django_db
@pytest.mark.parametrize(
    "current_url",
    [
        "https://evil.example.com/admin/",
        "//evil.example.com/admin/",
        "javascript:alert(1)",
        "http://testserver//evil.example.com/",
    ],
)
def test_htmx_foreign_current_url_falls_back_to_request_path(client, current_url):
    res = htmx(client, ADMIN_CHANGELIST + "?q=1", current_url=current_url)

    path, query = split_hx_redirect(res)
    assert path == reverse("admin:login")
    assert query == {"next": [ADMIN_CHANGELIST + "?q=1"]}


@pytest.mark.django_db
def test_htmx_missing_current_url_falls_back_to_request_path(client):
    res = htmx(client, ADMIN_CHANGELIST, current_url=None)

    _path, query = split_hx_redirect(res)
    assert query == {"next": [ADMIN_CHANGELIST]}


@pytest.mark.django_db
def test_htmx_from_login_page_does_not_reload_it(client):
    # The browser already shows the login page: an HX-Redirect to it would
    # only reload it (forever, if something on it polls).
    res = htmx(
        client,
        ADMIN_CHANGELIST,
        current_url="http://testserver" + reverse("admin:login"),
    )

    assert res.status_code == 204
    assert "HX-Redirect" not in res


@pytest.mark.django_db
def test_htmx_non_login_redirect_unchanged(client):
    # A redirect that does not lead to a login page is left to HTMX.
    res = htmx(client, "/admin")

    assert res.status_code == 301
    assert "HX-Redirect" not in res


def test_login_paths_contains_known_login_pages():
    paths = login_paths()

    assert reverse("admin:login") in paths
    assert reverse("login_form") in paths
