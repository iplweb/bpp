import pytest

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
