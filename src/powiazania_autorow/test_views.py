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
def test_dane_zawiera_tytul_orcid_pbn(client):
    from bpp.models import Tytul

    tytul = baker.make(Tytul, skrot="prof. dr hab.")
    centrum = baker.make(Autor, pokazuj=True)
    sasiad = baker.make(
        Autor,
        imiona="Anna",
        nazwisko="Nowak",
        pokazuj=True,
        tytul=tytul,
        orcid="0000-0002-1825-0097",
    )
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=sasiad, shared_publications_count=2
    )

    url = reverse("bpp:browse_autor_powiazania_dane", args=[centrum.pk])
    data = client.get(url).json()

    n = data["neighbors"][0]
    assert n["tytul"] == "prof. dr hab."
    assert n["orcid"] == "0000-0002-1825-0097"
    assert n["pbn_url"] == ""  # brak pbn_uid -> brak linku do PBN
    assert "total_works" in n  # liczba wszystkich prac (rozmiar węzła)
    assert isinstance(n["total_works"], int)
    assert "if_sum" in n  # sumaryczny IF (alternatywna metryka rozmiaru)
    assert "pk_sum" in n  # sumaryczny PK
    # centrum też ma komplet kluczy (bez tytułu/orcid -> puste stringi)
    assert data["center"]["tytul"] == ""
    assert data["center"]["orcid"] == ""
    assert data["center"]["pbn_url"] == ""
    assert isinstance(data["center"]["total_works"], int)
    assert "if_sum" in data["center"]
    assert "pk_sum" in data["center"]


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
def test_siec_bfs_dwa_poziomy(client):
    centrum = baker.make(Autor, pokazuj=True)
    a = baker.make(Autor, pokazuj=True)
    b = baker.make(Autor, pokazuj=True)
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=a, shared_publications_count=5
    )
    AuthorConnection.objects.create(
        primary_author=a, secondary_author=b, shared_publications_count=3
    )

    url = reverse("bpp:browse_autor_powiazania_siec", args=[centrum.pk])
    data = client.get(url, {"depth": 2, "topn": 10}).json()

    assert data["center_id"] == centrum.pk
    poziomy = {n["id"]: n["level"] for n in data["nodes"]}
    assert poziomy == {centrum.pk: 0, a.pk: 1, b.pk: 2}
    rodzice = {n["id"]: n["parent"] for n in data["nodes"]}
    assert rodzice[centrum.pk] is None
    assert rodzice[a.pk] == centrum.pk
    assert rodzice[b.pk] == a.pk
    assert data["truncated"] is False
    # krawędzie drzewa rozwijania
    pary = {(e["source"], e["target"]) for e in data["edges"]}
    assert (centrum.pk, a.pk) in pary
    assert (a.pk, b.pk) in pary


@pytest.mark.django_db
def test_siec_depth1_to_tylko_pierscien(client):
    centrum = baker.make(Autor, pokazuj=True)
    a = baker.make(Autor, pokazuj=True)
    b = baker.make(Autor, pokazuj=True)
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=a, shared_publications_count=5
    )
    AuthorConnection.objects.create(
        primary_author=a, secondary_author=b, shared_publications_count=3
    )

    url = reverse("bpp:browse_autor_powiazania_siec", args=[centrum.pk])
    data = client.get(url, {"depth": 1}).json()

    ids = {n["id"] for n in data["nodes"]}
    assert centrum.pk in ids and a.pk in ids
    assert b.pk not in ids  # poziom 2 poza zasięgiem depth=1


@pytest.mark.django_db
def test_siec_pomija_ukrytych_autorow(client):
    centrum = baker.make(Autor, pokazuj=True)
    ukryty = baker.make(Autor, pokazuj=False)
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=ukryty, shared_publications_count=5
    )

    url = reverse("bpp:browse_autor_powiazania_siec", args=[centrum.pk])
    data = client.get(url, {"depth": 3}).json()

    assert {n["id"] for n in data["nodes"]} == {centrum.pk}
    assert data["nodes"][0]["level"] == 0


@pytest.mark.django_db
def test_siec_extra_edges_poprzeczne(client):
    centrum = baker.make(Autor, pokazuj=True)
    a = baker.make(Autor, pokazuj=True)
    b = baker.make(Autor, pokazuj=True)
    # trójkąt: centrum-A, centrum-B (drzewo) oraz A-B (krawędź poprzeczna)
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=a, shared_publications_count=5
    )
    AuthorConnection.objects.create(
        primary_author=centrum, secondary_author=b, shared_publications_count=4
    )
    AuthorConnection.objects.create(
        primary_author=a, secondary_author=b, shared_publications_count=3
    )

    url = reverse("bpp:browse_autor_powiazania_siec", args=[centrum.pk])
    data = client.get(url, {"depth": 2, "topn": 10}).json()

    tree = {tuple(sorted((e["source"], e["target"]))) for e in data["edges"]}
    assert tuple(sorted((centrum.pk, a.pk))) in tree
    assert tuple(sorted((centrum.pk, b.pk))) in tree

    extra = {tuple(sorted((e["source"], e["target"]))) for e in data["extra_edges"]}
    assert tuple(sorted((a.pk, b.pk))) in extra
    # krawędzi drzewa nie ma w poprzecznych
    assert tuple(sorted((centrum.pk, a.pk))) not in extra


@pytest.mark.django_db
def test_siec_404_dla_nieistniejacego_autora(client):
    url = reverse("bpp:browse_autor_powiazania_siec", args=[99999])
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


def test_przelicznik_jest_w_celerybeat():
    from django.conf import settings

    nazwy_taskow = {wpis["task"] for wpis in settings.CELERYBEAT_SCHEDULE.values()}
    assert "powiazania_autorow.calculate_author_connections" in nazwy_taskow
