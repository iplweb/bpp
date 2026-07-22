import pytest
from django.urls import NoReverseMatch, reverse


def test_rest_api_jednostka_detail(client, jednostka):
    res = client.get(reverse("api_v1:jednostka-detail", args=(jednostka.pk,)))
    assert res.status_code == 200


def test_rest_api_jednostka_list(client, jednostka):
    res = client.get(reverse("api_v1:jednostka-list"))
    assert res.status_code == 200


def test_rest_api_wydzial_endpoint_removed():
    # Faza C (#438): model Wydzial znika — zasób /api/v1/wydzial/ nie istnieje.
    # „Wydział" to top-level Jednostka, więc dostępny jest wyłącznie przez
    # /api/v1/jednostka/.
    with pytest.raises(NoReverseMatch):
        reverse("api_v1:wydzial-list")
