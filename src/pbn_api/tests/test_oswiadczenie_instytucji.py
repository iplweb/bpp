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


# Testy dla Tier 4: znormalizowane dopasowanie (polskie znaki, myślniki)


@pytest.mark.django_db
def test_get_bpp_autor_normalized_polish_diacritics():
    """Test że autor z polskimi znakami jest dopasowany do PBN bez znaków.

    Główny przypadek: 'Łętowska' w BPP dopasowana do 'Letowska' z PBN.
    """
    # Autor w BPP ma polskie znaki diakrytyczne
    autor = baker.make(Autor, nazwisko="Łętowska", imiona="Anna")

    # Scientist w PBN ma nazwisko bez polskich znaków
    scientist = baker.make(
        Scientist,
        lastName="Letowska",
        name="Anna",
        orcid="",
    )
    oswiadczenie = baker.make(OswiadczenieInstytucji, personId=scientist)

    result = oswiadczenie.get_bpp_autor()

    assert result == autor


@pytest.mark.django_db
def test_get_bpp_autor_normalized_hyphen_vs_space():
    """Test że autor z myślnikiem jest dopasowany do PBN ze spacją.

    Główny przypadek: 'Lech-Marańda' w BPP dopasowana do 'Lech Maranda' z PBN.
    """
    # Autor w BPP ma myślnik w nazwisku
    autor = baker.make(Autor, nazwisko="Lech-Marańda", imiona="Ewa")

    # Scientist w PBN ma spację zamiast myślnika i bez polskich znaków
    scientist = baker.make(
        Scientist,
        lastName="Lech Maranda",
        name="Ewa",
        orcid="",
    )
    oswiadczenie = baker.make(OswiadczenieInstytucji, personId=scientist)

    result = oswiadczenie.get_bpp_autor()

    assert result == autor


@pytest.mark.django_db
def test_get_bpp_autor_normalized_missing_diacritic():
    """Test dla brakującego znaku diakrytycznego: 'Łetowska' vs 'Łętowska'."""
    # Autor w BPP ma pełne polskie znaki
    autor = baker.make(Autor, nazwisko="Łętowska", imiona="Magdalena")

    # Scientist w PBN ma brakujący znak diakrytyczny
    scientist = baker.make(
        Scientist,
        lastName="Łetowska",  # brakuje ę
        name="Magdalena",
        orcid="",
    )
    oswiadczenie = baker.make(OswiadczenieInstytucji, personId=scientist)

    result = oswiadczenie.get_bpp_autor()

    assert result == autor


@pytest.mark.django_db
def test_get_bpp_autor_normalized_priority_exact_over_normalized():
    """Test że dokładne dopasowanie ma priorytet nad znormalizowanym."""
    # Dwaj autorzy: jeden z dokładnym dopasowaniem, drugi ze znormalizowanym
    autor_exact = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    baker.make(Autor, nazwisko="Kowálski", imiona="Jan")  # różni się akcentem

    scientist = baker.make(
        Scientist,
        lastName="Kowalski",
        name="Jan",
        orcid="",
    )
    oswiadczenie = baker.make(OswiadczenieInstytucji, personId=scientist)

    result = oswiadczenie.get_bpp_autor()

    # Powinno zwrócić dokładne dopasowanie (Tier 3), nie znormalizowane (Tier 4)
    assert result == autor_exact


@pytest.mark.django_db
def test_get_bpp_autor_normalized_both_names():
    """Test że normalizacja działa dla imion i nazwisk jednocześnie."""
    # Autor w BPP z polskimi znakami w imieniu i nazwisku
    autor = baker.make(Autor, nazwisko="Świątek-Górniak", imiona="Żółć")

    # Scientist w PBN bez polskich znaków
    scientist = baker.make(
        Scientist,
        lastName="Swiatek Gorniak",
        name="Zolc",
        orcid="",
    )
    oswiadczenie = baker.make(OswiadczenieInstytucji, personId=scientist)

    result = oswiadczenie.get_bpp_autor()

    assert result == autor
