from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils.timezone import localtime
from model_bakery import baker


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


@pytest.mark.django_db
def test_rest_api_autor_filter_nazwisko_czesciowe(api_client, autor_jan_kowalski):
    res = api_client.get(reverse("api_v1:autor-list") + "?nazwisko=kowal")
    assert res.json()["count"] == 1


@pytest.mark.django_db
def test_rest_api_autor_filter_nazwisko_case_insensitive(
    api_client, autor_jan_kowalski
):
    res = api_client.get(reverse("api_v1:autor-list") + "?nazwisko=KOWALSKI")
    assert res.json()["count"] == 1


@pytest.mark.django_db
def test_rest_api_autor_filter_nazwisko_brak(api_client, autor_jan_kowalski):
    res = api_client.get(reverse("api_v1:autor-list") + "?nazwisko=nieistnieje")
    assert res.json()["count"] == 0


@pytest.mark.django_db
def test_rest_api_autor_list_nie_ujawnia_emaila_anonimowi(client):
    # RODO: adres e-mail autora to dane osobowe i nie może wyciekać
    # anonimowemu klientowi API (harvesting adresów).
    baker.make("bpp.Autor", email="sekret@example.com")
    res = client.get(reverse("api_v1:autor-list"))
    assert res.status_code == 200
    assert "sekret@example.com" not in res.content.decode()
    assert "email" not in res.json()["results"][0]


@pytest.mark.django_db
def test_rest_api_autor_list_ukrywa_dane_autorow_ukrytych(client):
    # Autor z pokazuj_w_api=False zostaje na liście (hiperłącza z publikacji
    # nie mogą prowadzić do 404), ale tylko jako okrojony obiekt.
    baker.make("bpp.Autor", nazwisko="Widoczny")
    ukryty = baker.make("bpp.Autor", nazwisko="Ukryty", pokazuj_w_api=False)
    res = client.get(reverse("api_v1:autor-list"))
    wyniki = res.json()["results"]
    assert {r.get("nazwisko") for r in wyniki} == {"Widoczny", None}
    assert {"id": ukryty.pk, "dane_ukryte": True} in wyniki
    assert "Ukryty" not in res.content.decode()


@pytest.mark.django_db
def test_rest_api_autor_detail_ukryty_dane_ukryte(client):
    ukryty = baker.make("bpp.Autor", nazwisko="Ukryty", pokazuj_w_api=False)
    res = client.get(reverse("api_v1:autor-detail", args=(ukryty.pk,)))
    assert res.status_code == 200
    assert res.json() == {"id": ukryty.pk, "dane_ukryte": True}


@pytest.mark.django_db
def test_rest_api_autor_filtr_nie_dopasowuje_ukrytych(client):
    # Dopasowanie okrojonego obiektu po ?nazwisko= ujawniałoby tożsamość.
    baker.make("bpp.Autor", nazwisko="Przykladowska", pokazuj_w_api=False)
    res = client.get(reverse("api_v1:autor-list"), {"nazwisko": "Przykladowska"})
    assert res.json()["count"] == 0
