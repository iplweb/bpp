import pytest
from django.contrib.contenttypes.models import ContentType
from django.test import Client
from django.urls import reverse
from model_bakery import baker

from komparator_pbn_udzialy.models import BrakAutoraWPublikacji, RozbieznoscDyscyplinPBN


@pytest.mark.django_db
def test_problemy_pbn_list_view_empty(client: Client):
    """Test widoku listy problemów PBN gdy brak danych."""
    url = reverse("komparator_pbn_udzialy:list")
    response = client.get(url)

    assert response.status_code == 200
    assert "Problemy PBN" in response.content.decode()
    assert "Nie znaleziono żadnych problemów" in response.content.decode()


@pytest.mark.django_db
def test_problemy_pbn_list_view_with_rozbieznosc(client: Client):
    """Test widoku listy z rozbieżnością dyscyplin."""
    autor = baker.make("bpp.Autor")
    jednostka = baker.make("bpp.Jednostka")
    wydawnictwo = baker.make("bpp.Wydawnictwo_Ciagle")
    wydawnictwo_autor = baker.make(
        "bpp.Wydawnictwo_Ciagle_Autor",
        autor=autor,
        jednostka=jednostka,
        rekord=wydawnictwo,
    )
    dyscyplina_bpp = baker.make("bpp.Dyscyplina_Naukowa", nazwa="Informatyka")
    dyscyplina_pbn = baker.make("bpp.Dyscyplina_Naukowa", nazwa="Matematyka")
    publikacja_pbn = baker.make("pbn_api.Publication", year=2023)
    oswiadczenie = baker.make(
        "pbn_api.OswiadczenieInstytucji",
        publicationId=publikacja_pbn,
    )

    content_type = ContentType.objects.get_for_model(wydawnictwo_autor)

    RozbieznoscDyscyplinPBN.objects.create(
        content_type=content_type,
        object_id=wydawnictwo_autor.pk,
        oswiadczenie_instytucji=oswiadczenie,
        dyscyplina_bpp=dyscyplina_bpp,
        dyscyplina_pbn=dyscyplina_pbn,
    )

    url = reverse("komparator_pbn_udzialy:list")
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()
    assert "Różne dyscypliny" in content
    assert str(autor) in content


@pytest.mark.django_db
def test_problemy_pbn_list_view_with_brak_autora(client: Client):
    """Test widoku listy z brakującym autorem."""
    pbn_scientist = baker.make("pbn_api.Scientist", name="Jan", lastName="Kowalski")
    publikacja_pbn = baker.make("pbn_api.Publication", year=2024, title="Test article")
    oswiadczenie = baker.make(
        "pbn_api.OswiadczenieInstytucji",
        personId=pbn_scientist,
        publicationId=publikacja_pbn,
    )

    BrakAutoraWPublikacji.objects.create(
        autor=None,
        pbn_scientist=pbn_scientist,
        oswiadczenie_instytucji=oswiadczenie,
        typ=BrakAutoraWPublikacji.TYP_BRAK_AUTORA_W_BPP,
    )

    url = reverse("komparator_pbn_udzialy:list")
    response = client.get(url)

    assert response.status_code == 200
    content = response.content.decode()
    assert "Jan Kowalski [PBN]" in content
    assert "Autor nie istnieje w BPP" in content


@pytest.mark.django_db
def test_problemy_pbn_list_view_filter_by_typ(client: Client):
    """Test filtrowania widoku po typie problemu."""
    pbn_scientist = baker.make("pbn_api.Scientist", name="Anna", lastName="Nowak")
    publikacja_pbn = baker.make("pbn_api.Publication", year=2023)
    oswiadczenie = baker.make(
        "pbn_api.OswiadczenieInstytucji",
        personId=pbn_scientist,
        publicationId=publikacja_pbn,
    )

    BrakAutoraWPublikacji.objects.create(
        autor=None,
        pbn_scientist=pbn_scientist,
        oswiadczenie_instytucji=oswiadczenie,
        typ=BrakAutoraWPublikacji.TYP_BRAK_PUBLIKACJI,
    )

    # Filtruj po typie brak_autora - nie powinno być wyników
    url = reverse("komparator_pbn_udzialy:list")
    response = client.get(url, {"filter": BrakAutoraWPublikacji.TYP_BRAK_AUTORA_W_BPP})

    assert response.status_code == 200
    content = response.content.decode()
    assert "Nie znaleziono żadnych problemów" in content

    # Filtruj po typie brak_publikacji - powinien być wynik
    response = client.get(url, {"filter": BrakAutoraWPublikacji.TYP_BRAK_PUBLIKACJI})

    assert response.status_code == 200
    content = response.content.decode()
    assert "Anna Nowak [PBN]" in content


@pytest.mark.django_db
def test_problemy_pbn_list_view_statistics(client: Client):
    """Test statystyk w widoku listy."""
    pbn_scientist = baker.make("pbn_api.Scientist")
    oswiadczenie1 = baker.make(
        "pbn_api.OswiadczenieInstytucji",
        personId=pbn_scientist,
    )
    oswiadczenie2 = baker.make(
        "pbn_api.OswiadczenieInstytucji",
        personId=pbn_scientist,
    )

    # Utwórz dwa różne problemy
    BrakAutoraWPublikacji.objects.create(
        pbn_scientist=pbn_scientist,
        oswiadczenie_instytucji=oswiadczenie1,
        typ=BrakAutoraWPublikacji.TYP_BRAK_AUTORA_W_BPP,
    )
    BrakAutoraWPublikacji.objects.create(
        pbn_scientist=pbn_scientist,
        oswiadczenie_instytucji=oswiadczenie2,
        typ=BrakAutoraWPublikacji.TYP_BRAK_POWIAZANIA,
    )

    url = reverse("komparator_pbn_udzialy:list")
    response = client.get(url)

    assert response.status_code == 200
    # Sprawdź że statystyki są w kontekście
    assert response.context["brakujacy_total"] == 2
    assert response.context["missing_autor_count"] == 1
    assert response.context["missing_link_count"] == 1
    assert response.context["total_count"] == 2
