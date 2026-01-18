import pytest

from bpp.models import Charakter_Formalny, Crossref_Mapper
from crossref_bpp.core import Komparator, StatusPorownania


def test_Komparator_porownaj_DOI_zadne():
    assert Komparator.porownaj_DOI(None).status == StatusPorownania.BLAD


@pytest.mark.django_db
def test_Komparator_porownaj_DOI_puste():
    assert Komparator.porownaj_DOI("nie ma takiego doi").status == StatusPorownania.BRAK


@pytest.mark.django_db
def test_Komparator_porownaj_DOI_obecne(wydawnictwo_ciagle):
    DOI = "10.500/foobar"
    wydawnictwo_ciagle.doi = DOI
    wydawnictwo_ciagle.save()

    assert (
        Komparator.porownaj_DOI("  10.500/FOOBAR").status == StatusPorownania.DOKLADNE
    )


@pytest.mark.django_db
def test_Komparator_porownaj_DOI_liczne(wydawnictwo_ciagle, wydawnictwo_zwarte):
    DOI = "10.500/foobar"

    for wydawnictwo in wydawnictwo_zwarte, wydawnictwo_ciagle:
        wydawnictwo.doi = DOI
        wydawnictwo_ciagle.save()

    assert (
        Komparator.porownaj_DOI("  10.500/FOOBAR").status == StatusPorownania.DOKLADNE
    )


@pytest.mark.django_db
def test_porownaj_autor_orcid_z_x(autor_jan_kowalski):
    autor_jan_kowalski.orcid = "123x"
    autor_jan_kowalski.save()

    wartosc = {"orcid": "123X"}
    ret = Komparator.porownaj_author(wartosc)
    assert ret.status == StatusPorownania.DOKLADNE
    assert ret.opis.find("ORCID") >= 0


def test_porownaj_type_unknown_type():
    """Test that unknown CrossRef type returns BLAD status."""
    ret = Komparator.porownaj_type("nieznany-typ")
    assert ret.status == StatusPorownania.BLAD
    assert "nie zdefiniowano" in ret.opis


@pytest.mark.django_db
def test_porownaj_type_no_mapping():
    """Test that known CrossRef type without BPP mapping returns BLAD status."""
    # Ensure no mapping exists for journal-article
    Crossref_Mapper.objects.filter(
        charakter_crossref=Crossref_Mapper.CHARAKTER_CROSSREF.JOURNAL_ARTICLE
    ).delete()

    # Create mapper without charakter_formalny_bpp
    Crossref_Mapper.objects.create(
        charakter_crossref=Crossref_Mapper.CHARAKTER_CROSSREF.JOURNAL_ARTICLE,
        charakter_formalny_bpp=None,
    )

    ret = Komparator.porownaj_type("journal-article")
    assert ret.status == StatusPorownania.BLAD
    assert "Crossref Mapper" in ret.opis


@pytest.mark.django_db
def test_porownaj_type_with_mapping_returns_charakter_formalny(charaktery_formalne):
    """Test that porownaj_type returns Charakter_Formalny, not Crossref_Mapper.

    This test verifies the fix for the bug where porownaj_type() was returning
    the Crossref_Mapper object instead of the actual Charakter_Formalny object.
    """
    # Get a Charakter_Formalny (e.g., KSP = "Książka w języku polskim")
    charakter_ksiazka = charaktery_formalne["KSP"]

    # Ensure no mapping exists for book type
    Crossref_Mapper.objects.filter(
        charakter_crossref=Crossref_Mapper.CHARAKTER_CROSSREF.BOOK
    ).delete()

    # Create mapper with proper charakter_formalny_bpp
    mapper = Crossref_Mapper.objects.create(
        charakter_crossref=Crossref_Mapper.CHARAKTER_CROSSREF.BOOK,
        charakter_formalny_bpp=charakter_ksiazka,
    )

    ret = Komparator.porownaj_type("book")

    assert ret.status == StatusPorownania.DOKLADNE
    assert ret.rekord_po_stronie_bpp is not None

    # The returned object should be Charakter_Formalny, NOT Crossref_Mapper
    returned_object = ret.rekord_po_stronie_bpp
    assert isinstance(returned_object, Charakter_Formalny), (
        f"Expected Charakter_Formalny, got {type(returned_object).__name__}"
    )

    # The PK should match the Charakter_Formalny PK, not the Crossref_Mapper PK
    assert returned_object.pk == charakter_ksiazka.pk
    assert returned_object.pk != mapper.pk


@pytest.mark.django_db
def test_porownaj_type_returns_correct_charakter_formalny_pk(charaktery_formalne):
    """Test that the PK of returned object matches Charakter_Formalny, not Crossref_Mapper.

    This test ensures that when helpers.py calls .pk on the result,
    it gets the Charakter_Formalny PK for the admin form initial data.
    """
    charakter_rozdzial = charaktery_formalne["ROZ"]

    Crossref_Mapper.objects.filter(
        charakter_crossref=Crossref_Mapper.CHARAKTER_CROSSREF.BOOK_CHAPTER
    ).delete()

    Crossref_Mapper.objects.create(
        charakter_crossref=Crossref_Mapper.CHARAKTER_CROSSREF.BOOK_CHAPTER,
        charakter_formalny_bpp=charakter_rozdzial,
    )

    ret = Komparator.porownaj_type("book-chapter")
    charakter_formalny_pk = ret.rekord_po_stronie_bpp.pk

    # Verify the PK can be used to retrieve the correct Charakter_Formalny
    retrieved = Charakter_Formalny.objects.get(pk=charakter_formalny_pk)
    assert retrieved.skrot == "ROZ"
