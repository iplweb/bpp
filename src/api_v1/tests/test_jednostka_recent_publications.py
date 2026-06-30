import pytest
from django.urls import reverse
from model_bakery import baker
from rest_framework.test import APIClient

from bpp.models import Autor, Jednostka, Wydawnictwo_Ciagle


@pytest.mark.django_db
def test_jednostka_recent_publications_endpoint(typy_odpowiedzialnosci):
    """Podstawowa struktura odpowiedzi dla endpointu jednostki."""
    client = APIClient()

    jednostka = baker.make(Jednostka, nazwa="Katedra Testowa")
    autor = baker.make(Autor, nazwisko="Jednostkowy", imiona="Jan")
    publikacja = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Praca jednostki")
    publikacja.dodaj_autora(autor, jednostka, typ_odpowiedzialnosci_skrot="aut.")

    url = reverse(
        "api_v1:recent_unit_publications-detail", kwargs={"pk": jednostka.pk}
    )
    response = client.get(url)

    assert response.status_code == 200
    data = response.json()
    assert data["jednostka_id"] == jednostka.pk
    assert "Testowa" in data["jednostka_nazwa"]
    assert data["count"] == 1
    pub = data["publications"][0]
    assert {"id", "opis_bibliograficzny", "rok", "ostatnio_zmieniony", "url"} <= set(
        pub
    )


@pytest.mark.django_db
def test_jednostka_recent_publications_rekurencyjnie(typy_odpowiedzialnosci):
    """Embed jednostki nadrzędnej zawiera dorobek jej pod-jednostek
    (poddrzewo wydział → katedra → zakład)."""
    client = APIClient()

    nadrzedna = baker.make(Jednostka, nazwa="Wydział Nadrzędny")
    podrzedna = baker.make(Jednostka, nazwa="Zakład Podrzędny", parent=nadrzedna)
    Jednostka.objects.rebuild()

    autor = baker.make(Autor, nazwisko="Podrzedny", imiona="Piotr")
    publikacja = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Praca zakładu")
    publikacja.dodaj_autora(autor, podrzedna, typ_odpowiedzialnosci_skrot="aut.")

    url = reverse(
        "api_v1:recent_unit_publications-detail", kwargs={"pk": nadrzedna.pk}
    )
    data = client.get(url).json()
    assert data["count"] == 1


@pytest.mark.django_db
def test_jednostka_recent_publications_po_slugu(typy_odpowiedzialnosci):
    """Endpoint jednostki przyjmuje slug obok numerycznego ID."""
    client = APIClient()

    jednostka = baker.make(Jednostka, nazwa="Katedra Slugowa")
    autor = baker.make(Autor, nazwisko="Sluggy", imiona="Sara")
    publikacja = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Praca slug")
    publikacja.dodaj_autora(autor, jednostka, typ_odpowiedzialnosci_skrot="aut.")

    assert jednostka.slug
    url = reverse(
        "api_v1:recent_unit_publications-detail", kwargs={"pk": jednostka.slug}
    )
    data = client.get(url).json()
    assert data["jednostka_id"] == jednostka.pk
    assert data["count"] == 1


@pytest.mark.django_db
def test_jednostka_recent_publications_404():
    """Nieistniejąca jednostka → 404."""
    client = APIClient()
    url = reverse(
        "api_v1:recent_unit_publications-detail", kwargs={"pk": 999999}
    )
    assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_jednostka_recent_publications_niewidoczna_404():
    """Jednostka niewidoczna publicznie nie ma embedu → 404."""
    client = APIClient()
    jednostka = baker.make(Jednostka, nazwa="Niewidoczna Katedra", widoczna=False)
    url = reverse(
        "api_v1:recent_unit_publications-detail", kwargs={"pk": jednostka.pk}
    )
    assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_jednostka_recent_publications_ukryty_status_pominiety(
    uczelnia, przed_korekta, typy_odpowiedzialnosci
):
    """Rekord o statusie ukrytym w kontekście 'api' nie wycieka przez embed
    jednostki."""
    client = APIClient()

    jednostka = baker.make(Jednostka, nazwa="Katedra Statusowa")
    autor = baker.make(Autor, nazwisko="Statusowy", imiona="Stefan")
    widoczna = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Widoczna")
    widoczna.dodaj_autora(autor, jednostka, typ_odpowiedzialnosci_skrot="aut.")
    ukryta = baker.make(
        Wydawnictwo_Ciagle, tytul_oryginalny="Ukryta", status_korekty=przed_korekta
    )
    ukryta.dodaj_autora(autor, jednostka, typ_odpowiedzialnosci_skrot="aut.")

    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)

    url = reverse(
        "api_v1:recent_unit_publications-detail", kwargs={"pk": jednostka.pk}
    )
    data = client.get(url).json()
    assert data["count"] == 1
    assert "Ukryta" not in " ".join(
        p["opis_bibliograficzny"] for p in data["publications"]
    )
