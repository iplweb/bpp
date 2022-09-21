import pytest

from crossref_bpp.models import CrossrefAPICache


@pytest.mark.django_db
def test_CrossrefAPICacheManager_cleanup():
    CrossrefAPICache.objects.cleanup()


@pytest.mark.django_db
def test_CrossrefAPICacheManager_get_by_doi(mocker):
    with mocker.patch.object(
        CrossrefAPICache.objects, "api_get_by_doi", return_value={"a": "b"}
    ):
        data = CrossrefAPICache.objects.get_by_doi("whatever")
    assert data["a"] == "b"


@pytest.mark.django_db
def test_CrossrefAPICacheManager_get_by_doi_no_queries(
    mocker, django_assert_max_num_queries
):
    with django_assert_max_num_queries(5):
        with mocker.patch.object(
            CrossrefAPICache.objects, "api_get_by_doi", return_value={"a": "b"}
        ):
            CrossrefAPICache.objects.get_by_doi("whatever")
            CrossrefAPICache.objects.get_by_doi("whatever")
            CrossrefAPICache.objects.get_by_doi("whatever")
