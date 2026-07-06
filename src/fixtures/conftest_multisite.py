"""Fixtures for multi-site (multi-hosted) testing.

Provides two universities (uczelnie) with linked Sites, staff users
with per-site access, and helper utilities for simulating requests
to different domains.
"""

import pytest
from django.contrib.sites.models import Site
from django.test import RequestFactory
from model_bakery import baker

from bpp.models import BppUser, Jednostka, Uczelnia, Wydzial


@pytest.fixture
def site1(db):
    """Site for the first university."""
    site, _ = Site.objects.update_or_create(
        pk=1,
        defaults={"domain": "uczelnia1.localhost", "name": "Uczelnia 1"},
    )
    return site


@pytest.fixture
def site2(db):
    """Site for the second university."""
    return Site.objects.create(domain="uczelnia2.localhost", name="Uczelnia 2")


@pytest.fixture
def uczelnia1(site1):
    """First university linked to site1."""
    uczelnia, _ = Uczelnia.objects.get_or_create(
        skrot="U1",
        defaults={"nazwa": "Uczelnia Pierwsza", "site": site1},
    )
    if uczelnia.site != site1:
        uczelnia.site = site1
        uczelnia.save(update_fields=["site"])
    return uczelnia


@pytest.fixture
def uczelnia2(site2):
    """Second university linked to site2."""
    return Uczelnia.objects.create(skrot="U2", nazwa="Uczelnia Druga", site=site2)


@pytest.fixture
def wydzial_uczelnia1(uczelnia1):
    """Faculty belonging to uczelnia1."""
    return Wydzial.objects.create(
        uczelnia=uczelnia1, skrot="W1-U1", nazwa="Wydział Pierwszy U1"
    )


@pytest.fixture
def wydzial_uczelnia2(uczelnia2):
    """Faculty belonging to uczelnia2."""
    return Wydzial.objects.create(
        uczelnia=uczelnia2, skrot="W1-U2", nazwa="Wydział Pierwszy U2"
    )


@pytest.fixture
def jednostka_uczelnia1(wydzial_uczelnia1):
    """Unit belonging to uczelnia1."""
    return Jednostka.objects.create(
        uczelnia=wydzial_uczelnia1.uczelnia,
        wydzial=wydzial_uczelnia1,
        skrot="J1-U1",
        nazwa="Jednostka Pierwsza U1",
    )


@pytest.fixture
def jednostka_uczelnia2(wydzial_uczelnia2):
    """Unit belonging to uczelnia2."""
    return Jednostka.objects.create(
        uczelnia=wydzial_uczelnia2.uczelnia,
        wydzial=wydzial_uczelnia2,
        skrot="J1-U2",
        nazwa="Jednostka Pierwsza U2",
    )


@pytest.fixture
def autor_uczelnia1(jednostka_uczelnia1, tytuly):
    """Author affiliated with uczelnia1."""
    autor = baker.make(
        "bpp.Autor",
        imiona="Jan",
        nazwisko="Testowy1",
        aktualna_jednostka=jednostka_uczelnia1,
    )
    baker.make(
        "bpp.Autor_Jednostka",
        autor=autor,
        jednostka=jednostka_uczelnia1,
    )
    return autor


@pytest.fixture
def autor_uczelnia2(jednostka_uczelnia2, tytuly):
    """Author affiliated with uczelnia2."""
    autor = baker.make(
        "bpp.Autor",
        imiona="Anna",
        nazwisko="Testowa2",
        aktualna_jednostka=jednostka_uczelnia2,
    )
    baker.make(
        "bpp.Autor_Jednostka",
        autor=autor,
        jednostka=jednostka_uczelnia2,
    )
    return autor


@pytest.fixture
def staff_user_uczelnia1(uczelnia1, db):
    """Staff user with access only to uczelnia1."""
    user = BppUser.objects.create_user(
        username="staff_u1",
        password="test12345",
        is_staff=True,
    )
    user.accessible_uczelnie.add(uczelnia1)
    return user


@pytest.fixture
def staff_user_uczelnia2(uczelnia2, db):
    """Staff user with access only to uczelnia2."""
    user = BppUser.objects.create_user(
        username="staff_u2",
        password="test12345",
        is_staff=True,
    )
    user.accessible_uczelnie.add(uczelnia2)
    return user


@pytest.fixture
def superuser_multisite(db):
    """Superuser — has access to all sites implicitly."""
    return BppUser.objects.create_superuser(
        username="super_multi",
        password="test12345",
    )


def make_request_for_site(site, path="/", user=None):
    """Create a request with HTTP_HOST set to the site's domain.

    Args:
        site: Site object whose domain to use as hostname.
        path: URL path for the request.
        user: Optional user to attach to request.

    Returns:
        HttpRequest with site resolution attributes set.
    """
    from bpp.middleware import SiteResolutionMiddleware

    factory = RequestFactory()
    request = factory.get(path, HTTP_HOST=site.domain)

    if user is not None:
        request.user = user
    else:
        from django.contrib.auth.models import AnonymousUser

        request.user = AnonymousUser()

    # Run middleware to set request.site and request._uczelnia
    mw = SiteResolutionMiddleware(lambda r: None)
    mw.process_request(request)
    return request
