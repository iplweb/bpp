"""Reguły porównywania wartości pól publikacji (``import_common.
porownanie_pol``) — wspólne dla wzbogacania rekordu i komparatora PBN."""

import pytest

from import_common import porownanie_pol as reguly


@pytest.mark.parametrize(
    "a,b",
    [
        ("1234-5678", "12345678"),
        ("978-83-01-00000-1", "978 83 01 00000 1"),
        ("83.01.00000.1", "8301000001"),
    ],
)
def test_numer_bez_kresek_kropek_i_odstepow(a, b):
    assert reguly.numer(a) == reguly.numer(b) != ""


@pytest.mark.parametrize("wartosc", [None, "", 12345678])
def test_numer_pusty(wartosc):
    assert reguly.numer(wartosc) == ""


def test_numer_rozroznia_wielkosc_litery_kontrolnej():
    assert reguly.numer("83-01-00000-x") != reguly.numer("83-01-00000-X")


@pytest.mark.parametrize(
    "wartosc",
    ["10.1/ABC", " 10.1/abc ", "https://doi.org/10.1/abc", "10.1/abc?jav=VoR"],
)
def test_doi_sam_numer(wartosc):
    assert reguly.doi(wartosc) == "10.1/abc"


def test_doi_zastane_nie_usuwa_adresu():
    assert reguly.doi_zastane(" 10.1/ABC ") == "10.1/abc"
    assert reguly.doi_zastane("https://doi.org/10.1/abc") != "10.1/abc"
    assert reguly.doi_zastane(None) == ""


def test_tekst_i_reguly_zastane():
    assert reguly.tekst(" <i>Tytuł</i>   pracy ") == "Tytuł pracy"
    assert reguly.tytul_bpp_zastany(" <i>Tytuł</i>   pracy ") == "Tytuł   pracy"
    assert reguly.tekst_zastany(" <i>Tytuł</i> ") == "<i>Tytuł</i>"
    assert reguly.tekst_zastany(None) == ""
    assert reguly.tekst_zastany(7) == "7"


@pytest.mark.parametrize("wartosc", ["10-20", "10–20", "10 — 20", " 10 - 20 "])
def test_strony(wartosc):
    assert reguly.strony(wartosc) == "10-20"


def test_adres_i_rok():
    assert reguly.adres(" https://a.pl/x/ ") == "https://a.pl/x"
    assert reguly.rok("2023") == reguly.rok(2023) == "2023"
    assert reguly.rok(None) == reguly.rok("b.r.") == ""
