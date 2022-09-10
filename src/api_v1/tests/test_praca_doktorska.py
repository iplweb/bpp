from datetime import timedelta

import pytest
from django.urls import reverse
from model_bakery import baker

from django.utils.timezone import localtime

from bpp.models import Praca_Doktorska


@pytest.mark.django_db
def test_praca_doktorska_charakter_formalny(praca_doktorska, charaktery_formalne):
    assert praca_doktorska.charakter_formalny.skrot == "D"


@pytest.mark.django_db
def test_praca_habilitacyjna_charakter_formalny(
    praca_habilitacyjna, charaktery_formalne
):
    assert praca_habilitacyjna.charakter_formalny.skrot == "H"


@pytest.mark.django_db
def test_rest_api_praca_doktorska_detail(client, praca_doktorska):
    res = client.get(
        reverse("api_v1:praca_doktorska-detail", args=(praca_doktorska.pk,))
    )
    assert res.status_code == 200


@pytest.mark.django_db
def test_rest_api_praca_doktorska_list(client, praca_doktorska):
    res = client.get(reverse("api_v1:praca_doktorska-list"))
    assert res.status_code == 200


@pytest.mark.django_db
def test_rest_api_praca_doktorska_filtering_1(api_client, praca_doktorska):
    czas = localtime(praca_doktorska.ostatnio_zmieniony).strftime("%Y-%m-%d %H:%M:%S")

    res = api_client.get(
        reverse("api_v1:praca_doktorska-list") + f"?ostatnio_zmieniony_after={czas}"
    )
    assert res.json()["count"] == 1


@pytest.mark.django_db
def test_rest_api_praca_doktorska_filtering_2(api_client, praca_doktorska):
    czas = localtime(
        praca_doktorska.ostatnio_zmieniony + timedelta(seconds=1)
    ).strftime("%Y-%m-%d %H:%M:%S")

    res = api_client.get(
        reverse("api_v1:praca_doktorska-list") + f"?ostatnio_zmieniony_after={czas}"
    )
    assert res.json()["count"] == 0


@pytest.mark.django_db
def test_rest_api_praca_doktorska_filtering_rok(api_client, praca_doktorska, rok):
    res = api_client.get(reverse("api_v1:praca_doktorska-list") + f"?rok_min={rok+1}")
    assert res.json()["count"] == 0


@pytest.mark.django_db
def test_rest_api_praca_doktorska_ukryj_status(
    api_client, praca_doktorska, uczelnia, przed_korekta, po_korekcie
):

    res = api_client.get(reverse("api_v1:praca_doktorska-list"))
    assert res.json()["count"] == 1

    praca_doktorska.status_korekty = przed_korekta
    praca_doktorska.save()

    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)
    res = api_client.get(reverse("api_v1:praca_doktorska-list"))
    assert res.json()["count"] == 0


@pytest.fixture
def wiele_prac_doktorskich(db, typy_odpowiedzialnosci):
    for a in range(100):
        baker.make(Praca_Doktorska)


@pytest.mark.django_db
def test_rest_api_praca_doktorska_no_queries(
    wiele_prac_doktorskich, django_assert_max_num_queries, api_client
):
    with django_assert_max_num_queries(11):
        api_client.get(reverse("api_v1:praca_doktorska-list"))
