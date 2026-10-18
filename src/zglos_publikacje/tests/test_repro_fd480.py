"""FD#480: pole „Link do publikacji lub DOI" przyjmuje DOI w dowolnej postaci.

Klient wkleja DOI bez ``https://`` (``10.xxxx/…``, ``doi:10.xxxx/…``,
``doi.org/…``) i formularz odrzucał to jako niepoprawny URL. Pole ma
rozpoznać identyfikator (jak „różdżka" Zotero) i zapisać kanoniczny URL.
"""

import pytest
from model_bakery import baker

from bpp.models import Uczelnia
from zglos_publikacje.forms import Zgloszenie_Publikacji_DaneForm
from zglos_publikacje.identyfikatory import normalizuj_identyfikator

DOI_URL = "https://doi.org/10.1016/j.cell.2020.01.001"


@pytest.mark.parametrize(
    "wpisane",
    [
        "10.1016/j.cell.2020.01.001",
        " 10.1016/j.cell.2020.01.001 ",
        "doi:10.1016/j.cell.2020.01.001",
        "DOI: 10.1016/j.cell.2020.01.001",
        "doi.org/10.1016/j.cell.2020.01.001",
        "dx.doi.org/10.1016/j.cell.2020.01.001",
        "http://dx.doi.org/10.1016/j.cell.2020.01.001",
        "https://dx.doi.org/10.1016/j.cell.2020.01.001",
        "http://doi.org/10.1016/j.cell.2020.01.001",
        "https://doi.org/10.1016/j.cell.2020.01.001",
        # kropka z końca zdania/cytowania nie należy do DOI
        "10.1016/j.cell.2020.01.001.",
    ],
)
def test_repro_fd480_doi_w_dowolnej_postaci(wpisane):
    assert normalizuj_identyfikator(wpisane) == DOI_URL


@pytest.mark.parametrize(
    "wpisane,oczekiwane",
    [
        ("PMID: 12345678", "https://pubmed.ncbi.nlm.nih.gov/12345678/"),
        ("pmid 12345678", "https://pubmed.ncbi.nlm.nih.gov/12345678/"),
        ("PMC1234567", "https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/"),
        ("PMCID: PMC1234567", "https://pmc.ncbi.nlm.nih.gov/articles/PMC1234567/"),
        ("arXiv:2101.00001", "https://arxiv.org/abs/2101.00001"),
        ("arxiv: hep-th/9901001", "https://arxiv.org/abs/hep-th/9901001"),
    ],
)
def test_repro_fd480_inne_identyfikatory(wpisane, oczekiwane):
    assert normalizuj_identyfikator(wpisane) == oczekiwane


@pytest.mark.parametrize(
    "wpisane",
    [
        "https://example.com/praca/123",
        "https://onlinelibrary.wiley.com/doi/10.1002/abc.123",
        # goła liczba / goły numer arXiv — zbyt niejednoznaczne, nie zgadujemy
        "12345678",
        "2101.00001",
        "",
    ],
)
def test_repro_fd480_reszta_bez_zmian(wpisane):
    assert normalizuj_identyfikator(wpisane) == wpisane


def _form(strona_www):
    return Zgloszenie_Publikacji_DaneForm(
        data={
            "tytul_oryginalny": "Test",
            "rok": 2024,
            "email": "test@example.com",
            "strona_www": strona_www,
            "zgoda_na_publikacje_pelnego_tekstu": "True",
        },
        rodzaj="ARTYKUL",
        forma_dostepu="OTWARTY",
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "wpisane,oczekiwane",
    [
        ("10.1016/j.cell.2020.01.001", DOI_URL),
        ("doi:10.1016/j.cell.2020.01.001", DOI_URL),
        ("PMID: 12345678", "https://pubmed.ncbi.nlm.nih.gov/12345678/"),
        ("www.example.com/praca", "https://www.example.com/praca"),
    ],
)
def test_repro_fd480_formularz_przyjmuje_i_normalizuje(wpisane, oczekiwane):
    baker.make(Uczelnia)
    form = _form(wpisane)
    assert form.is_valid(), form.errors
    assert form.cleaned_data["strona_www"] == oczekiwane


@pytest.mark.django_db
def test_repro_fd480_formularz_odrzuca_smieci():
    baker.make(Uczelnia)
    form = _form("to nie jest ani link, ani DOI")
    assert not form.is_valid()
    assert "DOI" in str(form.errors["strona_www"])


@pytest.mark.django_db
def test_repro_fd480_pole_nie_jest_input_type_url():
    """``type="url"`` zablokowałby goły DOI już w przeglądarce."""
    baker.make(Uczelnia)
    form = Zgloszenie_Publikacji_DaneForm(rodzaj="ARTYKUL", forma_dostepu="OTWARTY")
    html = str(form["strona_www"])
    assert 'type="text"' in html
    assert 'type="url"' not in html
