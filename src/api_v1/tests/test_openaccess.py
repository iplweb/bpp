import pytest
from django.urls import reverse

from bpp.models import Czas_Udostepnienia_OpenAccess


@pytest.mark.django_db
def test_rest_api_czas_udostepnienia_openaccess_detail(client, openaccess_data):
    pk = Czas_Udostepnienia_OpenAccess.objects.first().pk
    res = client.get(reverse("api_v1:czas_udostepnienia_openaccess-detail", args=(pk,)))
    assert res.status_code == 200


@pytest.mark.django_db
def test_rest_api_czas_udostepnienia_openaccess_list(client, openaccess_data):
    res = client.get(reverse("api_v1:czas_udostepnienia_openaccess-list"))
    assert res.status_code == 200
