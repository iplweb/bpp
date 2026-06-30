import pytest
from django.urls import reverse
from model_bakery import baker
from rest_framework.test import APIClient

from bpp.models import Autor, Wydawnictwo_Ciagle, Wydawnictwo_Ciagle_Autor


@pytest.mark.django_db
def test_autor_recent_publications_endpoint():
    """Test the recent_publications endpoint for authors."""
    client = APIClient()

    # Create test author
    autor = baker.make(Autor, nazwisko="Testowy", imiona="Jan")

    # Create some test publications
    for i in range(5):
        publikacja = baker.make(
            Wydawnictwo_Ciagle,
            tytul_oryginalny=f"Test publikacja {i}",
        )
        # Create author-publication relationship
        baker.make(Wydawnictwo_Ciagle_Autor, rekord=publikacja, autor=autor)

    # Test the endpoint
    url = reverse("api_v1:recent_author_publications-detail", kwargs={"pk": autor.pk})
    response = client.get(url)

    assert response.status_code == 200
    data = response.json()

    # Check response structure
    assert "autor_id" in data
    assert "autor_nazwa" in data
    assert "count" in data
    assert "publications" in data

    # Check autor information
    assert data["autor_id"] == autor.pk
    assert "Testowy" in data["autor_nazwa"]

    # Check publications
    assert isinstance(data["publications"], list)
    assert len(data["publications"]) <= 25  # Should return max 25 publications

    # Check publication structure
    if data["publications"]:
        pub = data["publications"][0]
        assert "id" in pub
        assert "opis_bibliograficzny" in pub
        assert "ostatnio_zmieniony" in pub
        assert "url" in pub


@pytest.mark.django_db
def test_autor_recent_publications_no_publications():
    """Test the endpoint when author has no publications."""
    client = APIClient()

    # Create test author without publications
    autor = baker.make(Autor, nazwisko="Bezpublikacji", imiona="Anna")

    url = reverse("api_v1:recent_author_publications-detail", kwargs={"pk": autor.pk})
    response = client.get(url)

    assert response.status_code == 200
    data = response.json()

    assert data["autor_id"] == autor.pk
    assert data["count"] == 0
    assert data["publications"] == []


@pytest.mark.django_db
def test_autor_recent_publications_nonexistent_author():
    """Test the endpoint with non-existent author ID."""
    client = APIClient()

    url = reverse("api_v1:recent_author_publications-detail", kwargs={"pk": 999999})
    response = client.get(url)

    assert response.status_code == 404


@pytest.mark.django_db
def test_autor_recent_publications_bez_duplikatow(
    typy_odpowiedzialnosci, autor_jan_kowalski, jednostka
):
    """Autor występujący na rekordzie dwukrotnie (np. autor i redaktor)
    nie może zduplikować publikacji w odpowiedzi (join do bpp_autorzy_mat
    wymaga DISTINCT)."""
    client = APIClient()

    publikacja = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Praca podwójna")
    publikacja.dodaj_autora(
        autor_jan_kowalski, jednostka, typ_odpowiedzialnosci_skrot="aut."
    )
    publikacja.dodaj_autora(
        autor_jan_kowalski, jednostka, typ_odpowiedzialnosci_skrot="red."
    )

    url = reverse(
        "api_v1:recent_author_publications-detail",
        kwargs={"pk": autor_jan_kowalski.pk},
    )
    response = client.get(url)

    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 1
    assert len(data["publications"]) == 1


@pytest.mark.django_db
def test_autor_recent_publications_po_slugu():
    """Endpoint przyjmuje slug autora obok numerycznego ID (czytelny snippet
    osadzania zgodny z URL-em profilu)."""
    client = APIClient()

    autor = baker.make(Autor, nazwisko="Slugowy", imiona="Adam")
    publikacja = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Praca slugowa")
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=publikacja, autor=autor)

    assert autor.slug
    url = reverse(
        "api_v1:recent_author_publications-detail", kwargs={"pk": autor.slug}
    )
    response = client.get(url)

    assert response.status_code == 200
    data = response.json()
    assert data["autor_id"] == autor.pk
    assert data["count"] == 1


@pytest.mark.django_db
def test_autor_recent_publications_profil_url():
    """Odpowiedź zawiera `profil_url` wskazujący stronę autora w BPP
    (link 'pełny profil' w stopce widgetu)."""
    client = APIClient()

    autor = baker.make(Autor, nazwisko="Profilowy", imiona="Filip")
    url = reverse(
        "api_v1:recent_author_publications-detail", kwargs={"pk": autor.pk}
    )
    data = client.get(url).json()
    assert "profil_url" in data
    assert autor.slug in data["profil_url"]


@pytest.mark.django_db
def test_autor_recent_publications_limit_param():
    """Parametr ?limit ogranicza liczbę pozycji; brak = domyślne 25."""
    client = APIClient()

    autor = baker.make(Autor, nazwisko="Limit", imiona="Leon")
    for i in range(30):
        publikacja = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny=f"Praca {i}")
        baker.make(Wydawnictwo_Ciagle_Autor, rekord=publikacja, autor=autor)

    base = reverse(
        "api_v1:recent_author_publications-detail", kwargs={"pk": autor.pk}
    )

    assert client.get(base).json()["count"] == 25
    assert client.get(base, {"limit": 5}).json()["count"] == 5


@pytest.mark.django_db
def test_autor_recent_publications_filtr_rok():
    """Parametry ?rok_od/?rok_do filtrują publikacje po roku."""
    client = APIClient()

    autor = baker.make(Autor, nazwisko="Rocznik", imiona="Roman")
    for rok in (2008, 2015, 2022):
        publikacja = baker.make(
            Wydawnictwo_Ciagle, tytul_oryginalny=f"Praca {rok}", rok=rok
        )
        baker.make(Wydawnictwo_Ciagle_Autor, rekord=publikacja, autor=autor)

    url = reverse(
        "api_v1:recent_author_publications-detail", kwargs={"pk": autor.pk}
    )

    data = client.get(url, {"rok_od": 2010, "rok_do": 2020}).json()
    assert data["count"] == 1
    assert data["publications"][0]["rok"] == 2015


@pytest.mark.django_db
def test_autor_recent_publications_zawiera_rok():
    """Odpowiedź zawiera pole `rok` dla każdej publikacji."""
    client = APIClient()

    autor = baker.make(Autor, nazwisko="Pole", imiona="Rok")
    publikacja = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Z rokiem", rok=2019)
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=publikacja, autor=autor)

    url = reverse(
        "api_v1:recent_author_publications-detail", kwargs={"pk": autor.pk}
    )
    pub = client.get(url).json()["publications"][0]
    assert pub["rok"] == 2019


@pytest.mark.django_db
def test_autor_recent_publications_niewidoczny_autor_404():
    """Autor oznaczony jako niewidoczny (pokazuj=False) nie ma embedu → 404."""
    client = APIClient()

    autor = baker.make(Autor, nazwisko="Ukryty", imiona="Urban", pokazuj=False)
    publikacja = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Niewidoczna")
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=publikacja, autor=autor)

    url = reverse(
        "api_v1:recent_author_publications-detail", kwargs={"pk": autor.pk}
    )
    assert client.get(url).status_code == 404


@pytest.mark.django_db
def test_autor_recent_publications_ukryty_status_pominiety(uczelnia, przed_korekta):
    """Rekord o statusie ukrytym w kontekście 'api' nie może wyciec przez
    endpoint embedu (regresja: dotąd endpoint nie filtrował widoczności)."""
    client = APIClient()

    autor = baker.make(Autor, nazwisko="Statusowy", imiona="Stefan")
    widoczna = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Widoczna")
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=widoczna, autor=autor)
    ukryta = baker.make(
        Wydawnictwo_Ciagle, tytul_oryginalny="Ukryta", status_korekty=przed_korekta
    )
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=ukryta, autor=autor)

    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)

    url = reverse(
        "api_v1:recent_author_publications-detail", kwargs={"pk": autor.pk}
    )
    data = client.get(url).json()
    opisy = " ".join(p["opis_bibliograficzny"] for p in data["publications"])
    assert "Ukryta" not in opisy
    assert data["count"] == 1


@pytest.mark.django_db
def test_autor_recent_publications_nie_pobiera_zbednych_kolumn():
    """Endpoint używa tylko kilku kolumn tabeli mat — nie może ciągnąć
    wszystkich ~47 kolumn, w szczególności tsvectora search_index."""
    from django.db import connection
    from django.test.utils import CaptureQueriesContext

    client = APIClient()

    autor = baker.make(Autor, nazwisko="Waski", imiona="Select")
    publikacja = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Praca wąska")
    baker.make(Wydawnictwo_Ciagle_Autor, rekord=publikacja, autor=autor)

    url = reverse("api_v1:recent_author_publications-detail", kwargs={"pk": autor.pk})
    with CaptureQueriesContext(connection) as ctx:
        response = client.get(url)

    assert response.status_code == 200
    selecty = [q["sql"] for q in ctx.captured_queries if "bpp_rekord_mat" in q["sql"]]
    assert selecty
    for sql in selecty:
        assert "search_index" not in sql
