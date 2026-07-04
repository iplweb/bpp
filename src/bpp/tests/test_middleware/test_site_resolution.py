import pytest
from django.contrib.auth.models import AnonymousUser
from django.test import RequestFactory

from bpp.middleware import SiteResolutionMiddleware
from fixtures.conftest_multisite import make_request_for_site

MULTISITE_HOSTS = [
    "uczelnia1.localhost",
    "uczelnia2.localhost",
    "unknown.localhost",
]


@pytest.fixture(autouse=True)
def _allow_test_hosts(settings):
    """Add test domains to ALLOWED_HOSTS for the duration of each test."""
    settings.ALLOWED_HOSTS = list(settings.ALLOWED_HOSTS) + MULTISITE_HOSTS


@pytest.mark.django_db
def test_middleware_resolves_site_from_hostname(site1, uczelnia1):
    """Request to uczelnia1.localhost resolves to site1."""
    request = make_request_for_site(site1)
    assert request.site == site1


@pytest.mark.django_db
def test_middleware_resolves_uczelnia_from_site(site1, uczelnia1):
    """request._uczelnia is the uczelnia linked to the resolved site."""
    request = make_request_for_site(site1)
    assert request._uczelnia == uczelnia1


@pytest.mark.django_db
def test_middleware_resolves_different_uczelnia_for_different_site(
    site1, site2, uczelnia1, uczelnia2
):
    """Different hostnames resolve to different uczelnie."""
    req1 = make_request_for_site(site1)
    req2 = make_request_for_site(site2)
    assert req1._uczelnia == uczelnia1
    assert req2._uczelnia == uczelnia2
    assert req1._uczelnia != req2._uczelnia


@pytest.mark.django_db
def test_middleware_fallback_to_site_id(uczelnia1, site1, settings):
    """Unknown hostname falls back to settings.SITE_ID."""
    settings.SITE_ID = site1.pk
    factory = RequestFactory()
    request = factory.get("/", HTTP_HOST="unknown.localhost")
    request.user = AnonymousUser()
    mw = SiteResolutionMiddleware(lambda r: None)
    mw.process_request(request)
    assert request.site == site1


@pytest.mark.django_db
def test_middleware_blocks_staff_without_access(site2, uczelnia2, staff_user_uczelnia1):
    """Staff user with access to site1 gets 403 on site2's admin."""
    request = make_request_for_site(site2, path="/admin/", user=staff_user_uczelnia1)
    mw = SiteResolutionMiddleware(lambda r: None)
    response = mw.process_view(request, None, [], {})
    assert response is not None
    assert response.status_code == 403


@pytest.mark.django_db
def test_middleware_allows_staff_with_correct_access(
    site1, uczelnia1, staff_user_uczelnia1
):
    """Staff user with access to site1 can access site1's admin."""
    request = make_request_for_site(site1, path="/admin/", user=staff_user_uczelnia1)
    mw = SiteResolutionMiddleware(lambda r: None)
    response = mw.process_view(request, None, [], {})
    assert response is None  # None means "continue processing"


@pytest.mark.django_db
def test_middleware_allows_superuser_everywhere(
    site1, site2, uczelnia1, uczelnia2, superuser_multisite
):
    """Superuser can access admin on any site."""
    for site in [site1, site2]:
        request = make_request_for_site(site, path="/admin/", user=superuser_multisite)
        mw = SiteResolutionMiddleware(lambda r: None)
        response = mw.process_view(request, None, [], {})
        assert response is None


@pytest.mark.django_db
def test_middleware_allows_anonymous_public_pages(site1, uczelnia1):
    """Anonymous user can access public pages."""
    request = make_request_for_site(site1, path="/bpp/")
    mw = SiteResolutionMiddleware(lambda r: None)
    response = mw.process_view(request, None, [], {})
    assert response is None


@pytest.mark.django_db
def test_middleware_allows_staff_with_no_sites_configured(site1, uczelnia1, db):
    """Staff with empty accessible_uczelnie is allowed (backward compat)."""
    from bpp.models import BppUser

    user = BppUser.objects.create_user(
        username="staff_no_sites", password="test", is_staff=True
    )
    # user.accessible_uczelnie is empty
    request = make_request_for_site(site1, path="/admin/", user=user)
    mw = SiteResolutionMiddleware(lambda r: None)
    response = mw.process_view(request, None, [], {})
    assert response is None  # allowed (backward compat)
