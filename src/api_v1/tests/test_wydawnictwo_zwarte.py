from datetime import timedelta

import pytest
from django.urls import reverse
from model_bakery import baker

from django.utils.timezone import localtime

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
        baker.make(Wydawnictwo_Zwarte)


@pytest.mark.django_db
def test_rest_api_wydawnictwo_zwarte_no_queries(
    wiele_wydawnictw_zwartych, django_assert_max_num_queries, api_client
):
    with django_assert_max_num_queries(11):
        api_client.get(reverse("api_v1:wydawnictwo_zwarte-list"))


TEKST_STRESZCZENIA = b"Tekst streszczenia"
TEXT_OF_SUMMARY = b"Text of summary"


@pytest.fixture
def wydawnictwo_zwarte_ze_streszczeniami(wydawnictwo_zwarte, jezyki):
    wydawnictwo_zwarte.streszczenia.create(
        jezyk_streszczenia=jezyki["pol."], streszczenie=TEKST_STRESZCZENIA
    )

    wydawnictwo_zwarte.streszczenia.create(
        jezyk_streszczenia=jezyki["ang."], streszczenie=TEXT_OF_SUMMARY
    )

    return wydawnictwo_zwarte


@pytest.mark.django_db
def test_rest_api_wydawnictwo_zwarte_streszczenia_eksport(
    wydawnictwo_zwarte_ze_streszczeniami, client
):
    res = client.get(
        reverse(
            "api_v1:wydawnictwo_zwarte-detail",
            args=(wydawnictwo_zwarte_ze_streszczeniami.pk,),
        )
    )

    for elem in res.json()["streszczenia"]:
        ts = client.get(elem)
        assert (TEXT_OF_SUMMARY in ts.content) or (TEKST_STRESZCZENIA in ts.content)
