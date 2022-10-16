import pytest

from crossref_bpp.forms import PobierzZCrossrefAPIForm
from crossref_bpp.models import CrossrefAPICache


@pytest.mark.vcr
@pytest.mark.django_db
def test_PobierzZCrossrefAPIFrom_clean():
    assert CrossrefAPICache.objects.count() == 0
    f = PobierzZCrossrefAPIForm({"identyfikator_doi": "10.1080/14786419.2014.955494"})
    assert f.is_valid()
    assert CrossrefAPICache.objects.count() == 1
