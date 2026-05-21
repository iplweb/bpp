from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils.timezone import localtime
from model_bakery import baker

from bpp.models import Patent


@pytest.mark.django_db
def test_rest_api_patent_detail(client, patent):
    res = client.get(reverse("api_v1:patent-detail", args=(patent.pk,)))
    assert res.status_code == 200


@pytest.mark.django_db
def test_rest_api_patent_list(client, patent):
    res = client.get(reverse("api_v1:patent-list"))
    assert res.status_code == 200


@pytest.mark.django_db
def test_rest_api_patent_filtering_1(api_client, patent):
    czas = localtime(patent.ostatnio_zmieniony).strftime("%Y-%m-%d %H:%M:%S")

    res = api_client.get(
        reverse("api_v1:patent-list") + f"?ostatnio_zmieniony_after={czas}"
    )
    assert res.json()["count"] == 1


@pytest.mark.django_db
def test_rest_api_patent_filtering_2(api_client, patent):
    czas = localtime(patent.ostatnio_zmieniony + timedelta(seconds=1)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    res = api_client.get(
        reverse("api_v1:patent-list") + f"?ostatnio_zmieniony_after={czas}"
    )
    assert res.json()["count"] == 0


@pytest.mark.django_db
def test_rest_api_patent_filtering_rok(api_client, wydawnictwo_ciagle, rok):
    res = api_client.get(reverse("api_v1:patent-list") + f"?rok_min={rok + 1}")
    assert res.json()["count"] == 0


@pytest.mark.django_db
def test_rest_api_patent_ukryj_status(
    api_client, patent, uczelnia, przed_korekta, po_korekcie
):

    res = api_client.get(reverse("api_v1:patent-list"))
    assert res.json()["count"] == 1

    patent.status_korekty = przed_korekta
    patent.save()

    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)
    res = api_client.get(reverse("api_v1:patent-list"))
    assert res.json()["count"] == 0


@pytest.fixture
def wiele_patentow(db, jezyki, charaktery_formalne):
    # Create one template object using baker.make to get all required fields with defaults
    template = baker.make(Patent)

    # Use bulk_create for 100x performance improvement over individual saves
    # Copy all fields from template except PK (id) and cached properties
    Patent.objects.bulk_create(
        [
            Patent(
                rok=template.rok,
                status_korekty=template.status_korekty,
                # Copy optional fields that have defaults
                tytul_oryginalny=template.tytul_oryginalny or f"Patent {i}",
            )
            for i in range(100)
        ]
    )


@pytest.mark.django_db
def test_rest_api_patent_no_queries(
    wiele_patentow, django_assert_max_num_queries, api_client
):
    with django_assert_max_num_queries(11):
        api_client.get(reverse("api_v1:patent-list"))
