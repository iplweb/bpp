"""Testy dla modelu OswiadczenieInstytucji."""

import pytest
from model_bakery import baker

from bpp.models import Autor
from pbn_api.models import OswiadczenieInstytucji, Scientist


@pytest.fixture
def scientist():
    """Utwórz naukowca PBN z danymi."""
    return baker.make(
        Scientist,
        lastName="Kowalski",
        name="Jan",
        orcid="0000-0001-2345-6789",
    )


@pytest.fixture
def oswiadczenie(scientist):
    """Utwórz oświadczenie instytucji."""
    return baker.make(OswiadczenieInstytucji, personId=scientist)


@pytest.mark.django_db
def test_get_bpp_autor_by_pbn_uid(oswiadczenie, scientist):
    """Test wyszukiwania autora po pbn_uid_id."""
    autor = baker.make(Autor, pbn_uid_id=scientist.pk)

    result = oswiadczenie.get_bpp_autor()

    assert result == autor


@pytest.mark.django_db
def test_get_bpp_autor_fallback_orcid(oswiadczenie, scientist):
    """Test fallback wyszukiwania po ORCID gdy brak pbn_uid."""
    autor = baker.make(Autor, orcid=scientist.orcid)

    result = oswiadczenie.get_bpp_autor()

    assert result == autor


@pytest.mark.django_db
def test_get_bpp_autor_fallback_name(oswiadczenie):
    """Test fallback wyszukiwania po imieniu i nazwisku."""
    autor = baker.make(
        Autor,
        nazwisko="Kowalski",
        imiona="Jan",
    )

    result = oswiadczenie.get_bpp_autor()

    assert result == autor


@pytest.mark.django_db
def test_get_bpp_autor_fallback_name_case_insensitive(oswiadczenie):
    """Test fallback wyszukiwania po imieniu i nazwisku - case insensitive."""
    autor = baker.make(
        Autor,
        nazwisko="KOWALSKI",
        imiona="JAN",
    )

    result = oswiadczenie.get_bpp_autor()

    assert result == autor


@pytest.mark.django_db
def test_get_bpp_autor_priority_pbn_uid_over_orcid(oswiadczenie, scientist):
    """Test że pbn_uid ma priorytet nad ORCID."""
    autor_by_pbn = baker.make(Autor, pbn_uid_id=scientist.pk)
    baker.make(Autor, orcid=scientist.orcid)

    result = oswiadczenie.get_bpp_autor()

    assert result == autor_by_pbn


@pytest.mark.django_db
def test_get_bpp_autor_priority_orcid_over_name(oswiadczenie, scientist):
    """Test że ORCID ma priorytet nad imieniem i nazwiskiem."""
    autor_by_orcid = baker.make(Autor, orcid=scientist.orcid)
    baker.make(Autor, nazwisko="Kowalski", imiona="Jan")

    result = oswiadczenie.get_bpp_autor()

    assert result == autor_by_orcid


@pytest.mark.django_db
def test_get_bpp_autor_returns_none_when_not_found(oswiadczenie):
    """Test że zwraca None gdy autor nie znaleziony."""
    result = oswiadczenie.get_bpp_autor()

    assert result is None


@pytest.mark.django_db
def test_get_bpp_autor_orcid_multiple_returns_skips_to_name():
    """Test że MultipleObjectsReturned dla ORCID przechodzi do wyszukiwania po nazwisku."""
    # Scientist bez ORCID żeby uniknąć tego fallbacku
    scientist_no_orcid = baker.make(
        Scientist,
        lastName="Nowak",
        name="Anna",
        orcid="",
    )
    oswiadczenie = baker.make(OswiadczenieInstytucji, personId=scientist_no_orcid)

    autor = baker.make(Autor, nazwisko="Nowak", imiona="Anna")

    result = oswiadczenie.get_bpp_autor()

    assert result == autor


@pytest.mark.django_db
def test_get_bpp_autor_name_multiple_returns_none():
    """Test że MultipleObjectsReturned dla nazwy zwraca None."""
    scientist = baker.make(
        Scientist,
        lastName="Kowalski",
        name="Jan",
        orcid="",
    )
    oswiadczenie = baker.make(OswiadczenieInstytucji, personId=scientist)

    # Dwóch autorów o tym samym imieniu i nazwisku
    baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    baker.make(Autor, nazwisko="Kowalski", imiona="Jan")

    result = oswiadczenie.get_bpp_autor()

    assert result is None
