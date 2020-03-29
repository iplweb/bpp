from django.test import TestCase
from django.urls import reverse


def test_rest_api_jednostka_detail(client, jednostka):
    res = client.get(reverse("api_v1:jednostka-detail", args=(jednostka.pk,)))
    assert res.status_code == 200


def test_rest_api_jednostka_list(client, jednostka):
    res = client.get(reverse("api_v1:jednostka-list"))
    assert res.status_code == 200
