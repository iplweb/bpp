import pytest
from django.urls import reverse
from model_bakery import baker

from bpp.models import Autor
from powiazania_autorow.models import AuthorConnection


@pytest.mark.django_db
def test_dane_zwraca_centrum_i_sasiadow_posortowanych(client):
    centrum = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pokazuj=True)
    a = baker.make(Autor, imiona="Anna", nazwisko="Nowak", pokazuj=True)
    b = baker.make(Autor, imiona="Bob", nazwisko="Zet", pokazuj=True)
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=a, shared_publications_count=2
    )
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=b, shared_publications_count=9
    )

    url = reverse("bpp:browse_autor_powiazania_dane", args=[centrum.pk])
    resp = client.get(url)

    assert resp.status_code == 200
    data = resp.json()
    assert data["center"]["id"] == centrum.pk
    assert data["center"]["label"] == "Jan Kowalski"
    labels = [n["label"] for n in data["neighbors"]]
    assert labels == ["Bob Zet", "Anna Nowak"]
    assert data["neighbors"][0]["shared"] == 9


@pytest.mark.django_db
def test_dane_dziala_gdy_autor_jest_secondary(client):
    centrum = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pokazuj=True)
    inny = baker.make(Autor, imiona="Ewa", nazwisko="Lis", pokazuj=True)
    AuthorConnection.objects.create(
        primary_author=inny, secondary_author=centrum, shared_publications_count=4
    )

    url = reverse("bpp:browse_autor_powiazania_dane", args=[centrum.pk])
    data = client.get(url).json()

    assert [n["label"] for n in data["neighbors"]] == ["Ewa Lis"]


@pytest.mark.django_db
def test_dane_pomija_autorow_z_pokazuj_false(client):
    centrum = baker.make(Autor, pokazuj=True)
    ukryty = baker.make(Autor, imiona="X", nazwisko="Ukryty", pokazuj=False)
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=ukryty, shared_publications_count=3
    )

    url = reverse("bpp:browse_autor_powiazania_dane", args=[centrum.pk])
    data = client.get(url).json()

    assert data["neighbors"] == []


@pytest.mark.django_db
def test_dane_pusty_gdy_brak_powiazan(client):
    centrum = baker.make(Autor, pokazuj=True)
    url = reverse("bpp:browse_autor_powiazania_dane", args=[centrum.pk])
    resp = client.get(url)
    assert resp.status_code == 200
    assert resp.json()["neighbors"] == []


@pytest.mark.django_db
def test_dane_404_dla_nieistniejacego_autora(client):
    url = reverse("bpp:browse_autor_powiazania_dane", args=[99999])
    assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_strona_grafu_renderuje_kontener(client):
    autor = baker.make(Autor, imiona="Jan", nazwisko="Kowalski", pokazuj=True)
    url = reverse("bpp:browse_autor_powiazania", args=[autor.pk])
    resp = client.get(url)
    assert resp.status_code == 200
    tresc = resp.content.decode("utf-8")
    assert 'id="cytoscape-container"' in tresc
    assert f'data-autor-id="{autor.pk}"' in tresc


@pytest.mark.django_db
def test_strona_grafu_404_dla_nieistniejacego_autora(client):
    url = reverse("bpp:browse_autor_powiazania", args=[99999])
    assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_strona_autora_ma_flage_powiazan_true(client):
    centrum = baker.make(Autor, pokazuj=True)
    sasiad = baker.make(Autor, pokazuj=True)
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=sasiad, shared_publications_count=1
    )
    resp = client.get(reverse("bpp:browse_autor", args=[centrum.pk]))
    assert resp.status_code == 200
    assert resp.context["ma_powiazania"] is True


@pytest.mark.django_db
def test_strona_autora_ma_flage_powiazan_false(client):
    centrum = baker.make(Autor, pokazuj=True)
    resp = client.get(reverse("bpp:browse_autor", args=[centrum.pk]))
    assert resp.context["ma_powiazania"] is False
