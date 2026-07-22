import pytest
from model_bakery import baker

from bpp.models import Autor, Tytul
from import_pracownikow.parsers.leksykony import (
    zbuduj_imiona_znane,
    zbuduj_parser_kontekst,
    zbuduj_probuj_match,
    zbuduj_tytuly,
)


@pytest.mark.django_db
def test_zbuduj_tytuly_laczy_baze_i_statyke():
    # Tytul.skrot/nazwa są unique, a baseline preloaduje słownik tytułów →
    # get_or_create zamiast baker.make (inaczej IntegrityError na setupie).
    Tytul.objects.get_or_create(
        skrot="prof. dr hab.", defaults={"nazwa": "profesor doktor habilitowany"}
    )
    tytuly = zbuduj_tytuly()
    assert "prof. dr hab." in tytuly  # z bazy (skrot, lower)
    assert "profesor doktor habilitowany" in tytuly  # z bazy (nazwa, lower)
    assert "dr" in tytuly  # ze statyki


@pytest.mark.django_db
def test_zbuduj_imiona_znane_splituje_i_lowercase():
    # Imiona SPOZA statyki (_IMIONA_STATYCZNE), żeby test faktycznie sprawdzał
    # split+lowercase Z BAZY, a nie trafiał w statyczny zbiór (tautologia).
    baker.make(Autor, nazwisko="Kowalski", imiona="Zdzisław Bonifacy")
    imiona = zbuduj_imiona_znane()
    assert "zdzisław" in imiona
    assert "bonifacy" in imiona


@pytest.mark.django_db
def test_zbuduj_probuj_match_true_dla_istniejacego_autora():
    baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    probuj = zbuduj_probuj_match()
    assert probuj("Jan", "Kowalski") is True
    assert probuj("Nieistniejacy", "Ktostam") is False


@pytest.mark.django_db
def test_zbuduj_parser_kontekst_spina_wszystko():
    baker.make(Autor, nazwisko="Nowak", imiona="Ewa")
    ctx = zbuduj_parser_kontekst()
    assert "dr" in ctx.tytuly
    assert "ewa" in ctx.imiona_znane
    assert ctx.probuj_match("Ewa", "Nowak") is True
