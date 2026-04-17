import pytest
from django.test import RequestFactory

from bpp.context_processors.orcid import orcid_auth_status


@pytest.mark.django_db
def test_orcid_auth_status_enabled(uczelnia_with_orcid):
    request = RequestFactory().get("/")
    ctx = orcid_auth_status(request)

    assert ctx["orcid_login_enabled"] is True


@pytest.mark.django_db
def test_orcid_auth_status_disabled(uczelnia_without_orcid):
    request = RequestFactory().get("/")
    ctx = orcid_auth_status(request)

    assert ctx["orcid_login_enabled"] is False


@pytest.mark.django_db
def test_orcid_auth_status_no_uczelnia(db):
    request = RequestFactory().get("/")
    ctx = orcid_auth_status(request)

    assert ctx["orcid_login_enabled"] is False
