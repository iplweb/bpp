from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils.timezone import localtime
from model_mommy import mommy

from bpp.models import Wydawnictwo_Zwarte


@pytest.mark.django_db
def test_rest_api_wydawnictwo_zwarte_detail(client, wydawnictwo_zwarte):
    res = client.get(
        reverse("api_v1:wydawnictwo_zwarte-detail", args=(wydawnictwo_zwarte.pk,))
    )
    assert res.status_code == 200


@pytest.mark.django_db
def test_rest_api_wydawnictwo_zwarte_list(client, wydawnictwo_zwarte):
    res = client.get(reverse("api_v1:wydawnictwo_zwarte-list"))
    assert res.status_code == 200


@pytest.mark.django_db
def test_rest_api_wydawnictwo_zwarte_filtering_1(api_client, wydawnictwo_zwarte):
    czas = localtime(wydawnictwo_zwarte.ostatnio_zmieniony).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    res = api_client.get(
        reverse("api_v1:wydawnictwo_zwarte-list") + f"?ostatnio_zmieniony_after={czas}"
    )
    assert res.json()["count"] == 1


@pytest.mark.django_db
def test_rest_api_wydawnictwo_zwarte_filtering_2(api_client, wydawnictwo_zwarte):
    czas = localtime(
        wydawnictwo_zwarte.ostatnio_zmieniony + timedelta(seconds=1)
    ).strftime("%Y-%m-%d %H:%M:%S")

    res = api_client.get(
        reverse("api_v1:wydawnictwo_zwarte-list") + f"?ostatnio_zmieniony_after={czas}"
    )
    assert res.json()["count"] == 0


@pytest.mark.django_db
def test_rest_api_wydawnictwo_zwarte_filtering_rok(api_client, wydawnictwo_ciagle, rok):
    res = api_client.get(
        reverse("api_v1:wydawnictwo_zwarte-list") + f"?rok_min={rok+1}"
    )
    assert res.json()["count"] == 0


@pytest.mark.django_db
def test_rest_api_wydawnictwo_zwarte_ukryj_status(
    api_client, wydawnictwo_zwarte, uczelnia, przed_korekta, po_korekcie
):

    res = api_client.get(reverse("api_v1:wydawnictwo_zwarte-list"))
    assert res.json()["count"] == 1

    wydawnictwo_zwarte.status_korekty = przed_korekta
    wydawnictwo_zwarte.save()

    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)
    res = api_client.get(reverse("api_v1:wydawnictwo_zwarte-list"))
    assert res.json()["count"] == 0


@pytest.fixture
def wiele_wydawnictw_zwartych(db):
    for a in range(100):
        mommy.make(Wydawnictwo_Zwarte)


@pytest.mark.django_db
def test_rest_api_wydawnictwo_zwarte_no_queries(
    wiele_wydawnictw_zwartych, django_assert_max_num_queries, api_client
):
    with django_assert_max_num_queries(11):
        api_client.get(reverse("api_v1:wydawnictwo_zwarte-list"))
