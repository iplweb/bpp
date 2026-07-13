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
    baker.make("bpp.Autor", email="sekret@example.com", pokazuj=True)
    res = client.get(reverse("api_v1:autor-list"))
    assert res.status_code == 200
    assert "sekret@example.com" not in res.content.decode()
    assert "email" not in res.json()["results"][0]


@pytest.mark.django_db
def test_rest_api_autor_list_pomija_autorow_ukrytych(client):
    # Autor z pokazuj=False jest świadomie ukryty ze stron publicznych —
    # nie może wyciekać przez listę API.
    baker.make("bpp.Autor", nazwisko="Widoczny", pokazuj=True)
    baker.make("bpp.Autor", nazwisko="Ukryty", pokazuj=False)
    res = client.get(reverse("api_v1:autor-list"))
    nazwiska = {r["nazwisko"] for r in res.json()["results"]}
    assert "Widoczny" in nazwiska
    assert "Ukryty" not in nazwiska


@pytest.mark.django_db
def test_rest_api_autor_detail_ukryty_niedostepny(client):
    ukryty = baker.make("bpp.Autor", pokazuj=False)
    res = client.get(reverse("api_v1:autor-detail", args=(ukryty.pk,)))
    assert res.status_code == 404
