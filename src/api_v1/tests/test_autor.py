from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils.timezone import localtime


@pytest.mark.django_db
def test_rest_api_autor_detail(client, autor):
    res = client.get(reverse("api_v1:autor-detail", args=(autor.pk,)))
    assert res.status_code == 200


@pytest.mark.django_db
def test_rest_api_autor_list(client, autor):
    res = client.get(reverse("api_v1:autor-list"))
    assert res.status_code == 200


@pytest.mark.django_db
def test_rest_api_autor_filtering_1(api_client, autor):
    czas = localtime(autor.ostatnio_zmieniony).strftime("%Y-%m-%d %H:%M:%S")

    res = api_client.get(
        reverse("api_v1:autor-list") + f"?ostatnio_zmieniony_after={czas}"
    )
    assert res.json()["count"] == 1


@pytest.mark.django_db
def test_rest_api_autor_filtering_2(api_client, autor):
    czas = localtime(autor.ostatnio_zmieniony + timedelta(seconds=1)).strftime(
        "%Y-%m-%d %H:%M:%S"
    )

    res = api_client.get(
        reverse("api_v1:autor-list") + f"?ostatnio_zmieniony_after={czas}"
    )
    assert res.json()["count"] == 0
