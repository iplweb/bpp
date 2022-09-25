import pytest

from crossref_bpp.views import pobierz_z_crossref
from pbn_api.tests.utils import middleware

from bpp.admin import Wydawnictwo_CiagleAdmin


@pytest.mark.vcr
@pytest.mark.django_db
def test_pobierz_z_crossref_nie_ma_rekordu(rf, admin_user, jezyki):
    req = rf.post("/", {"identyfikator_doi": "10.1080/1042819021000006394"})
    req.user = admin_user

    ret = pobierz_z_crossref(req, {}, Wydawnictwo_CiagleAdmin.crossref_templates)
    with middleware(req):
        assert "brak takiego DOI w bazie" in ret.rendered_content


@pytest.mark.vcr
@pytest.mark.django_db
def test_pobierz_z_crossref_form_errors(rf, admin_user):
    req = rf.post("/", {"identyfikator_doi": "aisjdfoasjdofaijsd"})
    req.user = admin_user

    ret = pobierz_z_crossref(req, {}, Wydawnictwo_CiagleAdmin.crossref_templates)
    with middleware(req):
        assert "nic po stronie CrossRef API" in ret.rendered_content
