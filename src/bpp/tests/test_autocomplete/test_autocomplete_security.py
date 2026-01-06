"""
Security tests for autocomplete functionality.

This module contains tests for:
- SQL injection prevention
- Input sanitization (special characters, long queries)
- Query truncation behavior
"""

import pytest
from django.urls import reverse

from bpp.views.autocomplete import (
    PublicAutorAutocomplete,
)

# SQL injection and special character test values
VALUES = [
    "Zi%C4%99ba+%5C",
    "Zi%C4%99ba+%5C \\",
    'fa\\"fa',
    "'",
    "fa ' fa",
    " ' fa",
    " fa '",
    "fa\\'fa",
    "Zięba \\",
    "Test ; test",
    "test (test)",
    "test & test",
    "test &",
    "& test",
    "; test",
    "test ;",
    ":*",
    ":",
    ":* :* *: *:",
    "",
    "\\",
    "123 \\ 123",
    "\\ 123",
    "123 \\",
    "|K",
]

AUTOCOMPLETES = [
    "bpp:public-autor-autocomplete",
    "bpp:jednostka-widoczna-autocomplete",
    "bpp:dyscyplina-autocomplete",
]


@pytest.mark.django_db
@pytest.mark.parametrize("autocomplete_name", AUTOCOMPLETES)
@pytest.mark.parametrize("qstr", VALUES)
def test_autocomplete_sql_injection_prevention(autocomplete_name, qstr, client):
    """Test that autocomplete endpoints handle special characters safely."""
    res = client.get(reverse(autocomplete_name), data={"q": qstr})
    assert res.status_code == 200


@pytest.mark.django_db
def test_public_autor_autocomplete_special_chars():
    """Test that PublicAutorAutocomplete handles parentheses and tabs."""
    from bpp.views.autocomplete import PublicAutorAutocomplete

    a = PublicAutorAutocomplete()
    a.q = "a (b)"
    assert list(a.get_queryset()) is not None

    a.q = "a\tb"
    assert list(a.get_queryset()) is not None


def test_tsquery_complex_input(admin_client):
    """Test handling of complex copy-pasted input strings.

    This tests a real-world scenario where a user pasted a complex
    multi-line report into the search field.
    """
    res = admin_client.get(
        "/bpp/public-autor-autocomplete/?q=Nazwa%20raportu%3A%09raport%20slot%C3%B3w"
        "%20-%20autor%09%09%09%09%09%09%20Autor%3A%09Krawiec%20Marcela%09%09%09%09%09"
        "%09%20Dyscyplina%3A%09rolnictwo%20i%20ogrodnictwo%20(4.2)%09%09%09%09%09%09"
        "%20Od%20roku%3A%092019%09%09%09%09%09%09%20Do%20roku%3A%092020%09%09%09%09%09"
        "%09%20Wygenerowano%3A%092020-02-14%207%3A19%3A44%09%09%09%09%09%09%20Wersja%20"
        "oprogramowania%20BPP%09202002.15%09%09%09%09%09%09%20%09%09%09%09%09%09%09%20"
        "Tytu%C5%82%20oryginalny%09Autorzy%09Rok%09%C5%B9r%C3%B3d%C5%82o%09Dyscyplina%09"
        "Punkty%20PK%09Punkty%20dla%20autora%09Slot%20Impact%20of%20seed%20light%20"
        "stimulation%20on%20the%20mechanical%20strength%20and%20photosynthetic%20pigments"
        "%20content%20in%20the%20scorzonera%20leaves%09Anna%20Ciupak%2C%20Agata%20"
        "Dziwulska-Hunek%2C%20Marcela%20Krawiec%2C%20Bo%C5%BCena%20G%C5%82adyszewska"
        "%092019%09Acta%20Agrophysica%09rolnictwo%20i%20ogrodnictwo%20(4.2)%0920%095"
        "%090%2C25%20EFFECT%20OF%20NATURAL%20FERTILIZATION%20AND%20CALCIUM%20CARBONATE"
        "%20ON%20YIELDING%20AND%20BIOLOGICAL%20VALUE%20OF%20THYME%20(%3Ci%3EThymus%20"
        "vulgaris%3C%2Fi%3E%20L.)%09Katarzyna%20Dzida%2C%20Zenia%20Micha%C5%82oj%C4%87"
        "%2C%20Zbigniew%20Jarosz%2C%20Karolina%20Pitura%2C%20Natalia%20Skubij%2C%20Daniel"
        "%20Skubij%2C%20Marcela%20Krawiec%092019%09Acta%20Scientiarum%20Polonorum-Hortorum"
        "%20Cultus%09rolnictwo%20i%20ogrodnictwo%20(4.2)%0970%0911%2C8322%090%2C169%20"
        "CHEMICAL%20%20AND%20%20NONCHEMICAL%20%20CONTROL%20%20OF%20%20WEEDS%20%20IN%20"
        "%20THE%20%20CULTIVATION%20%20OF%20%20LEMON%20%20BALM%20%20FOR%20%20SEEDS%09Marcela"
        "%20Krawiec%2C%20Andrzej%20Borowy%2C%20Katarzyna%20Dzida%092019%09Acta%20Scientiarum"
        "%20Polonorum-Hortorum%20Cultus%09rolnictwo%20i%20ogrodnictwo%20(4.2)%0970%0923"
        "%2C3333%090%2C3333"
    )
    assert res.status_code == 200


@pytest.mark.django_db
def test_autocomplete_input_sanitization_long_query(client):
    """Test that extremely long queries are truncated to prevent recursion issues."""
    # The actual query from the bug report (1766 characters)
    long_query = (
        "AAAAAAAAAAAA: 1987 AAAAA BBBBBBBBBB A AAAAAAAAA CCCCCCCCCC 1993 AAAAAAA "
        "AAAAAAA AA AAA. A. AAA. 2006 AAAAA BBBBBBBBBB A AAAAAAAAA DDDDDDDDDDDD "
        "1998 EEEEEEEEEEE II A AAAAA BBBBBBBBBB FFFFFF GGGGGGGGGG 1996 EEEEEEEEEEE "
        "I A AAAAAAAAA FFFFFF GGGGGGGGGG 1989 AAAAAAA AAAAAAA AA A. AAA. 1982 "
        "HHHHHH IIIIIII JJJJJJJJ KKKKKKKKKKKK LLLLLLLL: 2007 - MMMMMMMM NNNNNNN "
        "OOOOOOOOOOOOOO PPPPPPPP QQQQQ, AA. RRRRRRRR 78, SSSSSS 2004 - MMMMMMMM "
        "NNNNNNN OOOOOOOOOOOOOO TTTTTTTT, AA. UUUUUUUU 56V, SSSSSS 2004 - WWWWWWW "
        "A XXXXXXXX A YYYYYYY ZZZZZZZZZZZ, AAAAAAAAAA BBBBBBBB, SSSSSS 2004 - "
        "CCCC DDDDDDD EEEEEEEEEE A FFFFFF GGGGGG HH IIIIIIII JJJJJJJJ, KKKKKKKK "
        "1997 - 2004 LLLLLLLL MMMMMMMM-NNNNNNNNNNN A OOOOOOOO PPPPPP QQQQQQQQQQQ, "
        "RRRRRRRR SSSSSSSS, TTTTTT 1992 - UUUUUUU VVVVVVVV A WWWWWWWWWWW XXXXXXXXX "
        "YYYYYYYY ZZZZZZZZZ AA 7,AAAAAA 1997 - 1992 BBBBBBB A CCCCCCCCCCCC "
        "DDDDDDDDD EEEEEEEEE FFFFFFFFFF AA 7, GGGGGG 1982-1997 HHHHHHHH "
        "IIIIIIII-JJJJJJJJJJJJ A KKKKKKK A LLLLLLLLL MMMMMMMMMMMMM, NNNNNNNNN "
        "OOOOOOOO, PPPPPP QQQQQQQQQQ RRRRRRRRRRRR: 2015 - SSSSSSSSSSS TTTTTTTTTT "
        "A UUUUUUUUU VVVVVVVVVVVVV 2016 - WWWWWWWW XXXXXXXX YYYYYYYYYYYY A "
        "ZZZZZZZZZ AAAAAAAAAAA 2008 - BBBBBBBBBBBBB CCCCCCCCC DDDDDDDDDDD "
        "EEEEEEEEEE FFFFFFFFFFFFF GGGGGGGGGGGGGGGGGGG 2003 - HHHHHHHHHH II "
        "IIIIIIIII A JJJJJJJJJJJJJ KKKKKKKKK LLL MMMMMMM NNNNNNNNNNNNNNN OOO A "
        "PPPPPPPPP QQQQQQ RRRRRRRRRRRR A SSSSSSSS TTTTTTTTT 2004 - UUUUUUUUUUUU "
        "VVVVVV WWWWWWWWWWWWW A XXXX YY 9 2005 - ZZZZZZZZZZ AAAAAAAAAAAAA 5 "
        "BBBBBBB CCCCCCCC A DDDDDDDDD EEEEEEE FFFFFFFFFFF A GGGGGGGGGGGGGG 1991 "
        "- HHHHHH A IIIIIIIIII JJJJJJ KKKKKKKKKKKK II A III LLLL (3)"
    )

    assert len(long_query) > 120, "Test query should be longer than 120 characters"

    res = client.get(reverse("bpp:public-autor-autocomplete"), data={"q": long_query})
    assert res.status_code == 200, "Should not cause recursion error"


@pytest.mark.django_db
@pytest.mark.parametrize(
    "query_length,expected_status",
    [
        (119, 200),  # Just under the limit
        (120, 200),  # Exactly at the limit
        (121, 200),  # Just over the limit
        (500, 200),  # Moderately long
        (1000, 200),  # Very long
        (1766, 200),  # The exact length from the bug report
    ],
)
def test_autocomplete_input_sanitization_various_lengths(
    client, query_length, expected_status
):
    """Test that queries of various lengths are handled correctly."""
    query = "A" * query_length
    res = client.get(reverse("bpp:public-autor-autocomplete"), data={"q": query})
    assert res.status_code == expected_status


@pytest.mark.django_db
def test_autocomplete_truncation_unit_test():
    """Unit test that verifies the mixin truncates queries correctly."""
    ac = PublicAutorAutocomplete()

    # Create a mock request
    class MockRequest:
        method = "GET"
        GET = {"q": "A" * 200, "forward": "{}"}

    ac.setup(request=MockRequest())

    # Test that dispatch truncates the query
    ac.dispatch(MockRequest())

    assert hasattr(ac, "q")
    assert len(ac.q) == 120, (
        f"Query should be truncated to 120 characters, got {len(ac.q)}"
    )
    assert ac.q == "A" * 120


@pytest.mark.django_db
def test_autocomplete_normal_queries_unchanged():
    """Test that normal-length queries are not affected."""
    ac = PublicAutorAutocomplete()

    class MockRequest:
        method = "GET"
        GET = {"q": "Jan Kowalski", "forward": "{}"}

    ac.setup(request=MockRequest())

    ac.dispatch(MockRequest())

    assert hasattr(ac, "q")
    assert ac.q == "Jan Kowalski"
    assert len(ac.q) < 120


@pytest.mark.django_db
@pytest.mark.parametrize(
    "autocomplete_name",
    [
        "bpp:public-autor-autocomplete",
        "bpp:jednostka-widoczna-autocomplete",
        "bpp:dyscyplina-autocomplete",
        "bpp:public-konferencja-autocomplete",
        "bpp:public-wydzial-autocomplete",
        "bpp:zrodlo-autocomplete",
    ],
)
def test_autocomplete_long_query_multiple_endpoints(client, autocomplete_name):
    """Test that multiple autocomplete endpoints handle long queries correctly."""
    long_query = "X" * 500
    res = client.get(reverse(autocomplete_name), data={"q": long_query})
    assert res.status_code == 200
