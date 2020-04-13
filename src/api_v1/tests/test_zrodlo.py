from datetime import timedelta

from django.test import TestCase
from django.urls import reverse
from django.utils.timezone import localtime


def test_rest_api_zrodlo_detail(client, zrodlo):
    res = client.get(reverse("api_v1:zrodlo-detail", args=(zrodlo.pk,)))
    assert res.status_code == 200


def test_rest_api_zrodlo_list(client, zrodlo):
    res = client.get(reverse("api_v1:zrodlo-list"))
    assert res.status_code == 200


def test_rest_api_zrodlo_filtering_1(api_client, zrodlo):
    czas = localtime(zrodlo.ostatnio_zmieniony).strftime("%Y-%m-%d %H:%M:%S")

    res = api_client.get(
        reverse("api_v1:zrodlo-list") + f"?ostatnio_zmieniony_after={czas}"
    )
    assert res.json()["count"] == 1


def test_rest_api_zrodlo_filtering_2(api_client, zrodlo):

    czas = localtime(zrodlo.ostatnio_zmieniony + timedelta(seconds=1)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    res = api_client.get(
        reverse("api_v1:zrodlo-list") + f"?ostatnio_zmieniony_after={czas}"
    )
    assert res.json()["count"] == 0
