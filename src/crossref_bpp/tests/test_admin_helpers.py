import pytest

from crossref_bpp.admin.helpers import convert_crossref_to_changeform_initial_data
from crossref_bpp.models import CrossrefAPICache


@pytest.mark.vcr
@pytest.mark.django_db
def test_convert_crossref_to_changeform_initial_data_only_e_issn():
    z = CrossrefAPICache.objects.get_by_doi("10.3390/ijms24043114")

    ret = convert_crossref_to_changeform_initial_data(z)
    assert ret["issn"] is None


@pytest.mark.vcr
@pytest.mark.django_db
def test_convert_crossref_to_changeform_initial_data_both_issns():
    z = CrossrefAPICache.objects.get_by_doi("10.3390/ijms24043114")
    z["ISSN"] = ["1234-5678"]

    ret = convert_crossref_to_changeform_initial_data(z)
    assert ret["issn"] == "1234-5678"


@pytest.mark.vcr
@pytest.mark.django_db
def test_convert_crossref_to_changeform_initial_data_non_electronic_issn():
    z = CrossrefAPICache.objects.get_by_doi("10.3390/ijms24043114")
    z["issn-type"].append({"issn-type": "jakis-inny", "value": "1234-5678"})

    ret = convert_crossref_to_changeform_initial_data(z)
    assert ret["issn"] == "1234-5678"
