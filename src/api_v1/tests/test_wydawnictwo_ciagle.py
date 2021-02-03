from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils.timezone import localtime
from model_mommy import mommy

from bpp.models import Wydawnictwo_Ciagle


@pytest.mark.django_db
def test_rest_api_wydawnictwo_ciagle_detail(client, wydawnictwo_ciagle):
    res = client.get(
        reverse("api_v1:wydawnictwo_ciagle-detail", args=(wydawnictwo_ciagle.pk,))
    )
    assert res.status_code == 200


@pytest.mark.django_db
def test_rest_api_wydawnictwo_ciagle_list(client, wydawnictwo_ciagle):
    res = client.get(reverse("api_v1:wydawnictwo_ciagle-list"))
    assert res.status_code == 200


@pytest.mark.django_db
def test_rest_api_wydawnictwo_ciagle_filtering_1(api_client, wydawnictwo_ciagle):
    czas = localtime(wydawnictwo_ciagle.ostatnio_zmieniony).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    res = api_client.get(
        reverse("api_v1:wydawnictwo_ciagle-list") + f"?ostatnio_zmieniony_after={czas}"
    )
    assert res.json()["count"] == 1


@pytest.mark.django_db
def test_rest_api_wydawnictwo_ciagle_filtering_2(api_client, wydawnictwo_ciagle):
    czas = localtime(
        wydawnictwo_ciagle.ostatnio_zmieniony + timedelta(seconds=1)
    ).strftime("%Y-%m-%d %H:%M:%S")

    res = api_client.get(
        reverse("api_v1:wydawnictwo_ciagle-list") + f"?ostatnio_zmieniony_after={czas}"
    )
    assert res.json()["count"] == 0


@pytest.mark.django_db
def test_rest_api_wydawnictwo_ciagle_filtering_rok(api_client, wydawnictwo_ciagle, rok):
    res = api_client.get(
        reverse("api_v1:wydawnictwo_ciagle-list") + f"?rok_min={rok+1}"
    )
    assert res.json()["count"] == 0


@pytest.mark.django_db
def test_rest_api_wydawnictwo_ciagle_ukryj_status(
    api_client, wydawnictwo_ciagle, uczelnia, przed_korekta, po_korekcie
):

    res = api_client.get(reverse("api_v1:wydawnictwo_ciagle-list"))
    assert res.json()["count"] == 1

    wydawnictwo_ciagle.status_korekty = przed_korekta
    wydawnictwo_ciagle.save()

    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)
    res = api_client.get(reverse("api_v1:wydawnictwo_ciagle-list"))
    assert res.json()["count"] == 0


@pytest.fixture
def wiele_wydawnictw_ciaglych(db):
    for a in range(100):
        mommy.make(Wydawnictwo_Ciagle)


@pytest.mark.django_db
def test_rest_api_wydawnictwo_ciagle_no_queries(
    wiele_wydawnictw_ciaglych, django_assert_max_num_queries, api_client
):
    with django_assert_max_num_queries(11):
        api_client.get(reverse("api_v1:wydawnictwo_ciagle-list"))
