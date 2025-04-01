import datetime

import pytest

from import_common.core import normalize_date
from import_common.normalization import (
    normalize_doi,
    normalize_kod_dyscypliny,
    normalize_nazwa_dyscypliny,
    normalize_orcid,
    normalize_tytul_publikacji,
)


@pytest.mark.parametrize(
    "i,o",
    [
        ("101_0", "1.1"),
        ("111_0", "1.11"),
        ("407", "4.7"),
        ("411", "4.11"),
        ("1001", "10.1"),
        ("1010", "10.10"),
        ("4.1", "4.1"),
    ],
)
def test_normalize_kod_dyscypliny(i, o):
    assert normalize_kod_dyscypliny(i) == o


@pytest.mark.parametrize(
    "i,o",
    [
        (
            "http://dx.doi.org/10.1097/meg.0000000000000237",
            "10.1097/meg.0000000000000237",
        ),
        (
            "https://dx.doi.org/10.1097/meg.0000000000000237",
            "10.1097/meg.0000000000000237",
        ),
        ("DX.DOI.ORG/10.1097/MEG.0000000000000237", "10.1097/meg.0000000000000237"),
        (
            "   DX.DOI.ORG/10.1097/MEG.0000000000000237   ",
            "10.1097/meg.0000000000000237",
        ),
        (None, None),
        ("", None),
    ],
)
def test_normalize_doi(i, o):
    assert normalize_doi(i) == o


def test_normalize_nazwa_dyscypliny():
    NAZWA = "nauki o Ziemi i środowisku"
    assert normalize_nazwa_dyscypliny(NAZWA) == NAZWA


@pytest.mark.parametrize(
    "i,o",
    [
        ("http://orcid.org/0000-0003-2575-3642", "0000-0003-2575-3642"),
        ("https://orcid.org/0000-0003-2575-3642", "0000-0003-2575-3642"),
        ("HTTP://ORCiD.oRG/0000-0003-2575-3642", "0000-0003-2575-3642"),
        ("   HTTP://ORCiD.oRG/0000-0003-2575-3642", "0000-0003-2575-3642"),
    ],
)
def test_normalize_orcid(i, o):
    assert normalize_orcid(i) == o


@pytest.mark.parametrize(
    "i,o",
    [
        (
            "to jest tytul\nz nowa linia\n\n\nbo tak",
            "to jest tytul z nowa linia bo tak",
        ),
        ("wytniemy online [online]", "wytniemy online"),
        ("A duzych liter NIE SPRAWDZILEM", "A duzych liter NIE SPRAWDZILEM"),
    ],
)
def test_normalize_tytul_publikacji(i, o):
    assert normalize_tytul_publikacji(i) == o


@pytest.mark.parametrize(
    "i,o",
    [
        (None, None),
        ("", None),
        (" ", None),
        (" 2024.11.20 ", datetime.datetime(2024, 11, 20, 0, 0)),
        ("30.04.2021", datetime.datetime(2021, 4, 30, 0, 0)),
        (datetime.datetime(2020, 1, 1), datetime.datetime(2020, 1, 1, 0, 0)),
    ],
)
def test_normalize_date(i, o):
    assert normalize_date(i) == o
