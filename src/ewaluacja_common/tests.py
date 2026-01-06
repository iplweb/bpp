import pytest
from django.db import IntegrityError
from model_bakery import baker

from bpp.const import RODZAJ_PBN_ARTYKUL
from bpp.models import Autor, Dyscyplina_Naukowa
from ewaluacja_common.models import Rodzaj_Autora
from ewaluacja_common.utils import NieArtykul, get_lista_prac
from ewaluacja_liczba_n.models import IloscUdzialowDlaAutoraZaRok


@pytest.mark.django_db
def test_rodzaj_autora_str():
    """Test string representation of Rodzaj_Autora model."""
    # Create record for testing (don't rely on migration data)
    rodzaj, _ = Rodzaj_Autora.objects.get_or_create(
        skrot="N",
        defaults={"nazwa": "pracownik naukowy w liczbie N", "sort": 1},
    )
    assert str(rodzaj) == "N - pracownik naukowy w liczbie N"


@pytest.mark.django_db
def test_rodzaj_autora_skrot_unique():
    """Test unique constraint on skrot field."""
    baker.make(Rodzaj_Autora, skrot="X", nazwa="pierwszy", sort=100)

    with pytest.raises(IntegrityError):
        baker.make(Rodzaj_Autora, skrot="X", nazwa="drugi", sort=101)


@pytest.mark.django_db
def test_rodzaj_autora_ordering():
    """Test ordering by sort field."""
    # Clear existing records and create test data
    Rodzaj_Autora.objects.all().delete()

    rodzaj3 = baker.make(Rodzaj_Autora, skrot="C", nazwa="trzeci", sort=30)
    rodzaj1 = baker.make(Rodzaj_Autora, skrot="A", nazwa="pierwszy", sort=10)
    rodzaj2 = baker.make(Rodzaj_Autora, skrot="B", nazwa="drugi", sort=20)

    rodzaje = list(Rodzaj_Autora.objects.all())
    assert rodzaje[0] == rodzaj1
    assert rodzaje[1] == rodzaj2
    assert rodzaje[2] == rodzaj3


@pytest.mark.django_db
def test_rodzaj_autora_fields():
    """Test field values and defaults."""
    # Create record with specific fields for testing
    rodzaj, _ = Rodzaj_Autora.objects.get_or_create(
        skrot="N",
        defaults={
            "nazwa": "pracownik naukowy w liczbie N",
            "sort": 1,
            "jest_w_n": True,
            "licz_sloty": True,
        },
    )

    assert rodzaj.jest_w_n is True
    assert rodzaj.licz_sloty is True
    assert rodzaj.sort == 1


@pytest.mark.django_db
def test_get_lista_prac_raises_for_missing_discipline():
    """Test that get_lista_prac raises ValueError for nonexistent discipline."""
    with pytest.raises(ValueError) as exc_info:
        get_lista_prac("nieistniejaca dyscyplina")

    assert "Nie mam żadnych autorów" in str(exc_info.value)


@pytest.mark.django_db
def test_get_lista_prac_requires_ilosc_udzialow_records():
    """Test that get_lista_prac requires IloscUdzialowDlaAutoraZaRok records to exist."""
    # Create discipline without any IloscUdzialowDlaAutoraZaRok records
    baker.make(Dyscyplina_Naukowa, nazwa="Pusta dyscyplina", kod="9.9")

    # Should raise ValueError because no authors have contribution records
    with pytest.raises(ValueError) as exc_info:
        get_lista_prac("Pusta dyscyplina")

    assert "Nie mam żadnych autorów" in str(exc_info.value)


@pytest.mark.django_db
def test_nie_artykul_transform():
    """Test NieArtykul transform produces correct SQL."""
    transform = NieArtykul("rodzaj_pbn")
    expected_template = f"(%(expressions)s != {RODZAJ_PBN_ARTYKUL})"
    assert transform.template == expected_template


@pytest.mark.django_db
def test_get_lista_prac_queryset_structure():
    """Test that get_lista_prac returns QuerySet with proper structure."""
    # Create discipline with IloscUdzialowDlaAutoraZaRok records
    dyscyplina = baker.make(Dyscyplina_Naukowa, nazwa="Dyscyplina struktura", kod="5.5")
    autor = baker.make(Autor)

    # Create IloscUdzialowDlaAutoraZaRok to make autor "allowed"
    baker.make(
        IloscUdzialowDlaAutoraZaRok,
        autor=autor,
        dyscyplina_naukowa=dyscyplina,
        rok=2024,
        ilosc_udzialow=1,
        ilosc_udzialow_monografie=0,
    )

    # Call function - should return QuerySet (even if empty from the view)
    result = get_lista_prac("Dyscyplina struktura")

    # Verify it returns a QuerySet
    from django.db.models.query import QuerySet

    assert isinstance(result, QuerySet)

    # Verify queryset has proper annotations defined
    # (these are added via .annotate() call in get_lista_prac)
    query_str = str(result.query)
    assert "monografia" in query_str or "NieArtykul" in query_str
