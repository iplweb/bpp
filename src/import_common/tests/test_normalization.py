import datetime

import pytest

from import_common.core import normalize_date
from import_common.normalization import (
    extract_part_number,
    normalize_doi,
    normalize_kod_dyscypliny,
    normalize_nazwa_dyscypliny,
    normalize_orcid,
    normalize_part_number,
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
        # 4-digit codes with single-digit area (regression test for bug fix)
        ("2061", "2.61"),  # area 2, subdiscipline 61
        ("201", "2.1"),  # area 2, subdiscipline 1
        ("209", "2.9"),  # area 2, subdiscipline 9
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
        # DOI with URL query parameters should be stripped
        (
            "https://doi.org/10.1021/acs.jmedchem.2c01612?urlappend=%3Fref%3DPDF&jav=VoR&rel=cite-as",
            "10.1021/acs.jmedchem.2c01612",
        ),
        (
            "10.1021/acs.jmedchem.2c01612?foo=bar",
            "10.1021/acs.jmedchem.2c01612",
        ),
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


@pytest.mark.parametrize(
    "part,expected",
    [
        # Cyfry rzymskie
        ("I", 1),
        ("II", 2),
        ("III", 3),
        ("IV", 4),
        ("V", 5),
        ("VI", 6),
        ("VII", 7),
        ("VIII", 8),
        ("IX", 9),
        ("X", 10),
        # Małe litery
        ("ii", 2),
        ("iii", 3),
        ("iv", 4),
        # Cyfry arabskie
        ("1", 1),
        ("2", 2),
        ("10", 10),
        ("25", 25),
        # Edge cases
        (None, None),
        ("", None),
        ("  ", None),
        ("abc", None),
    ],
)
def test_normalize_part_number(part, expected):
    assert normalize_part_number(part) == expected


@pytest.mark.parametrize(
    "title,expected_part",
    [
        # cz. z cyfrą rzymską
        ("Znaczenie jakości wody w wielkostadnej produkcji drobiarskiej cz. II", 2),
        ("Znaczenie jakości wody w wielkostadnej produkcji drobiarskiej cz. III", 3),
        ("Tytuł publikacji cz. I", 1),
        ("Tytuł publikacji cz. IV", 4),
        ("Tytuł publikacji cz. V", 5),
        # cz. z cyfrą arabską
        ("Tytuł publikacji cz. 1", 1),
        ("Tytuł publikacji cz. 2", 2),
        ("Tytuł publikacji cz. 10", 10),
        # część z cyfrą rzymską
        ("Tytuł publikacji część I", 1),
        ("Tytuł publikacji część II", 2),
        # część z cyfrą arabską
        ("Tytuł publikacji część 1", 1),
        ("Tytuł publikacji część 2", 2),
        # tom
        ("Tytuł publikacji tom I", 1),
        ("Tytuł publikacji tom IV", 4),
        ("Tytuł publikacji tom 5", 5),
        # vol.
        ("Tytuł publikacji vol. I", 1),
        ("Tytuł publikacji vol. 5", 5),
        ("Tytuł publikacji vol 3", 3),
        # part
        ("Tytuł publikacji part I", 1),
        ("Tytuł publikacji part III", 3),
        ("Tytuł publikacji part 2", 2),
        # Case insensitive
        ("Tytuł publikacji CZ. II", 2),
        ("Tytuł publikacji Cz. III", 3),
        ("Tytuł publikacji CZĘŚĆ II", 2),
        ("Tytuł publikacji TOM IV", 4),
        ("Tytuł publikacji PART III", 3),
        ("Tytuł publikacji VOL. 5", 5),
        # Brak numeru części
        ("Tytuł bez numeru części", None),
        ("Inny tytuł publikacji", None),
        ("Tytuł z CZ w środku słowa RZECZ", None),
        # Edge cases
        (None, None),
    ],
)
def test_extract_part_number(title, expected_part):
    _, part = extract_part_number(title)
    assert part == expected_part


def test_extract_part_number_returns_title_without_part():
    """Sprawdza, że tytuł jest zwracany bez numeru części."""
    title = "Znaczenie jakości wody cz. II w produkcji"
    title_without_part, part = extract_part_number(title)
    assert part == 2
    assert "cz. II" not in title_without_part
    assert "Znaczenie jakości wody" in title_without_part
    assert "w produkcji" in title_without_part


def test_extract_part_number_similar_titles_different_parts():
    """Test głównego przypadku użytkownika - rozróżnianie cz. II i cz. III."""
    title1 = "Znaczenie jakości wody w wielkostadnej produkcji drobiarskiej cz. II"
    title2 = "Znaczenie jakości wody w wielkostadnej produkcji drobiarskiej cz. III"

    _, part1 = extract_part_number(title1)
    _, part2 = extract_part_number(title2)

    assert part1 == 2
    assert part2 == 3
    assert part1 != part2
