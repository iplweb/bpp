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
