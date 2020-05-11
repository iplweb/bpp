from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils.timezone import localtime


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
