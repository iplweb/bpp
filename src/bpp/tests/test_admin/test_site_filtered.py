import pytest
from django.contrib.admin.sites import AdminSite

from bpp.admin.jednostka import JednostkaAdmin
from bpp.admin.uczelnia import UczelniaAdmin
from bpp.admin.wydzial import WydzialAdmin
from bpp.models import Jednostka, Uczelnia, Wydzial
from fixtures.conftest_multisite import make_request_for_site

MULTISITE_DOMAINS = [
    "uczelnia1.localhost",
    "uczelnia2.localhost",
]


@pytest.fixture(autouse=True)
def _allow_multisite_hosts(settings):
    """Add test site domains to ALLOWED_HOSTS."""
    settings.ALLOWED_HOSTS = [
        *settings.ALLOWED_HOSTS,
        *MULTISITE_DOMAINS,
    ]


@pytest.mark.django_db
def test_jednostka_admin_filters_by_uczelnia(
    site1,
    uczelnia1,
    uczelnia2,
    jednostka_uczelnia1,
    jednostka_uczelnia2,
    staff_user_uczelnia1,
):
    """Staff user on site1 sees only jednostki from uczelnia1."""
    request = make_request_for_site(site1, path="/admin/", user=staff_user_uczelnia1)
    admin = JednostkaAdmin(Jednostka, AdminSite())
    qs = admin.get_queryset(request)
    assert jednostka_uczelnia1 in qs
    assert jednostka_uczelnia2 not in qs


@pytest.mark.django_db
def test_wydzial_admin_filters_by_uczelnia(
    site1,
    uczelnia1,
    uczelnia2,
    wydzial_uczelnia1,
    wydzial_uczelnia2,
    staff_user_uczelnia1,
):
    """Staff user on site1 sees only wydzialy from uczelnia1."""
    request = make_request_for_site(site1, path="/admin/", user=staff_user_uczelnia1)
    admin = WydzialAdmin(Wydzial, AdminSite())
    qs = admin.get_queryset(request)
    assert wydzial_uczelnia1 in qs
    assert wydzial_uczelnia2 not in qs


@pytest.mark.django_db
def test_superuser_sees_all_jednostki(
    site1,
    uczelnia1,
    uczelnia2,
    jednostka_uczelnia1,
    jednostka_uczelnia2,
    superuser_multisite,
):
    """Superuser sees jednostki from all uczelnie."""
    request = make_request_for_site(site1, path="/admin/", user=superuser_multisite)
    admin = JednostkaAdmin(Jednostka, AdminSite())
    qs = admin.get_queryset(request)
    assert jednostka_uczelnia1 in qs
    assert jednostka_uczelnia2 in qs


@pytest.mark.django_db
def test_uczelnia_admin_filters_for_non_superuser(
    site1,
    uczelnia1,
    uczelnia2,
    staff_user_uczelnia1,
):
    """Non-superuser sees only their own uczelnia."""
    request = make_request_for_site(site1, path="/admin/", user=staff_user_uczelnia1)
    admin = UczelniaAdmin(Uczelnia, AdminSite())
    qs = admin.get_queryset(request)
    assert uczelnia1 in qs
    assert uczelnia2 not in qs


@pytest.mark.django_db
def test_superuser_sees_all_uczelnie(
    site1,
    uczelnia1,
    uczelnia2,
    superuser_multisite,
):
    """Superuser sees all uczelnie."""
    request = make_request_for_site(site1, path="/admin/", user=superuser_multisite)
    admin = UczelniaAdmin(Uczelnia, AdminSite())
    qs = admin.get_queryset(request)
    assert uczelnia1 in qs
    assert uczelnia2 in qs
