import pytest

from bpp.admin import Wydawnictwo_CiagleAdmin
from bpp.models import Crossref_Mapper
from crossref_bpp.views import _czy_typ_jest_wydawnictwem_zwartym, pobierz_z_crossref
from pbn_api.tests.utils import middleware


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


@pytest.mark.django_db
def test_czy_typ_jest_wydawnictwem_zwartym_book():
    """Test that book types are correctly identified as wydawnictwo zwarte."""
    Crossref_Mapper.objects.get_or_create(
        charakter_crossref=Crossref_Mapper.CHARAKTER_CROSSREF.BOOK,
        defaults={"jest_wydawnictwem_zwartym": True},
    )
    assert _czy_typ_jest_wydawnictwem_zwartym("book") is True


@pytest.mark.django_db
def test_czy_typ_jest_wydawnictwem_zwartym_monograph():
    """Test that monograph type is correctly identified as wydawnictwo zwarte."""
    Crossref_Mapper.objects.get_or_create(
        charakter_crossref=Crossref_Mapper.CHARAKTER_CROSSREF.MONOGRAPH,
        defaults={"jest_wydawnictwem_zwartym": True},
    )
    assert _czy_typ_jest_wydawnictwem_zwartym("monograph") is True


@pytest.mark.django_db
def test_czy_typ_jest_wydawnictwem_zwartym_journal_article():
    """Test that journal-article is not identified as wydawnictwo zwarte."""
    Crossref_Mapper.objects.get_or_create(
        charakter_crossref=Crossref_Mapper.CHARAKTER_CROSSREF.JOURNAL_ARTICLE,
        defaults={"jest_wydawnictwem_zwartym": False},
    )
    assert _czy_typ_jest_wydawnictwem_zwartym("journal-article") is False


@pytest.mark.django_db
def test_czy_typ_jest_wydawnictwem_zwartym_unknown_type():
    """Test that unknown types return False."""
    assert _czy_typ_jest_wydawnictwem_zwartym("unknown-type") is False


def test_czy_typ_jest_wydawnictwem_zwartym_empty():
    """Test that empty type returns False."""
    assert _czy_typ_jest_wydawnictwem_zwartym("") is False
    assert _czy_typ_jest_wydawnictwem_zwartym(None) is False
