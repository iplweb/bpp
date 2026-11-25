"""Reguły porównywania wartości pól publikacji (``import_common.
porownanie_pol``) — jedne dla wzbogacania rekordu i komparatora PBN."""

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


def test_numer_znak_kontrolny_bez_rozrozniania_wielkosci_liter():
    assert reguly.numer("1234-567x") == reguly.numer("1234-567X") == "1234567X"


@pytest.mark.parametrize(
    "wartosc",
    ["10.1/ABC", " 10.1/abc ", "https://doi.org/10.1/abc", "10.1/abc?jav=VoR"],
)
def test_doi_sam_numer(wartosc):
    assert reguly.doi(wartosc) == "10.1/abc"


def test_tekst_bez_znacznikow_i_nadmiarowych_odstepow():
    assert reguly.tekst(" <i>Tytuł</i>   pracy ") == "Tytuł pracy"
    assert reguly.tekst(None) == ""
    assert reguly.odstepy(" a \n b ") == "a b"


@pytest.mark.parametrize("wartosc", ["10-20", "10–20", "10 — 20", " 10 - 20 "])
def test_strony(wartosc):
    assert reguly.strony(wartosc) == "10-20"


def test_adres_i_rok():
    assert reguly.adres(" https://a.pl/x/ ") == "https://a.pl/x"
    assert reguly.rok("2023") == reguly.rok(2023) == "2023"
    assert reguly.rok(None) == reguly.rok("b.r.") == ""
