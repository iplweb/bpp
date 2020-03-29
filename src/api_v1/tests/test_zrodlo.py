from django.test import TestCase
from django.urls import reverse


def test_rest_api_zrodlo_detail(client, zrodlo):
    res = client.get(reverse("api_v1:zrodlo-detail", args=(zrodlo.pk,)))
    assert res.status_code == 200


def test_rest_api_zrodlo_list(client, zrodlo):
    res = client.get(reverse("api_v1:zrodlo-list"))
    assert res.status_code == 200
