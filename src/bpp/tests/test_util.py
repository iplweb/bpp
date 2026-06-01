import pytest

from bpp.util import (
    fulltext_tokenize,
    knapsack,
    safe_streszczenie_html,
    strip_html,
    strip_nonalphanumeric,
    wytnij_isbn_z_uwag,
)


@pytest.mark.parametrize(
    "input,output,rest",
    [
        ("ISBN 978-83-7374-091-4, ten tego", "978-83-7374-091-4", "ten tego"),
        ("ISBN 83-200-1817-X", "83-200-1817-X", ""),
        ("tu nie ma ISBNu", None, None),
        ("ISBN-10 978-83-7374-091-4; ISBN-13 958498498894, ten tego", None, None),
    ],
)
def test_wytnij_isbn_z_uwag(input, output, rest):
    res = wytnij_isbn_z_uwag(input)
    if output is None:
        assert res is None
        return

    isbn, reszta = res
    assert isbn == output
    assert reszta == rest


def test_knapsack_empty():
    assert knapsack(10, [], [], []) == (0, [])


@pytest.mark.timeout(5)
def test_knapsack_very_long():
    # Test na optymalizacje sytuacji gdy chcemy dostac znacznie wiecej punktow niz wychdozi z danej listy,
    knapsack(99900, [1] * 99800, [1] * 99800, [1] * 99800)


def test_knapsack_zwracaj_liste():
    assert knapsack(
        10,
        [1, 2, 3, 4, 5],
        [1, 2, 3, 4, 5],
        [
            "a",
            "b",
            "c",
            "d",
            "e",
        ],
        True,
    ) == (10, ["d", "c", "b", "a"])


def test_knapsack_nie_zwracaj_listy():
    assert knapsack(
        10,
        [1, 2, 3, 4, 5],
        [1, 2, 3, 4, 5],
        [
            "a",
            "b",
            "c",
            "d",
            "e",
        ],
        zwracaj_liste_przedmiotow=False,
    ) == (10, [])


@pytest.mark.django_db
def test_ModelZOpisemBibliograficznym(wydawnictwo_ciagle):
    assert wydawnictwo_ciagle.opis_bibliograficzny() != ""


@pytest.mark.parametrize(
    "i,o", [("<b>test", "test"), ("<b>test</b>", "test"), ("", ""), (None, None)]
)
def test_strip_html(i, o):
    assert strip_html(i) == o


@pytest.mark.parametrize(
    "i, o",
    [("identyfikacja markerów molekularnych", "identyfikacja markerów molekularnych")],
)
def test_strip_nonalphanumeric(i, o):
    assert strip_nonalphanumeric(i) == o


def test_safe_streszczenie_html_math_less_than_is_escaped_not_swallowed():
    # Regresja: streszczenie "<30IU/dL ... <40IU/dL" (operator porównania,
    # bez zamykającego '>') było traktowane przez minifikator jak otwarty
    # znacznik i pożerało resztę strony (prawą kolumnę rekordu).
    raw = "VWF:Ag) of <30IU/dL or <40IU/dL, in which about 80% exhibited"
    out = safe_streszczenie_html(raw)
    assert "&lt;30IU/dL" in out
    assert "&lt;40IU/dL" in out
    assert "80% exhibited" in out


def test_safe_streszczenie_html_both_comparison_operators():
    raw = "moderate (FVIII >= 1%-<= 5%) or mild (FVIII >5%-<40%) haemophilia"
    out = safe_streszczenie_html(raw)
    # nic nie ginie, oba operatory uciekają do encji
    assert "&gt;= 1%-&lt;= 5%" in out
    assert "&gt;5%-&lt;40%" in out
    assert "haemophilia" in out


def test_safe_streszczenie_html_lt_followed_by_letter_no_data_loss():
    # "ct<or ≥15K" -- '<' tuż przy literze wygląda jak znacznik, ale jest
    # niedomknięty; nie wolno połknąć dalszego tekstu.
    raw = "baseline plt ct<or ≥15K/μL. Age (< or ≥65 y) TAIL"
    out = safe_streszczenie_html(raw)
    assert "ct&lt;or" in out
    assert "TAIL" in out


def test_safe_streszczenie_html_prose_resembling_tag_no_data_loss():
    # "<b and c>" mogłoby zostać zinterpretowane jako <b> z atrybutami;
    # nie tworzymy pogrubienia ani nie gubimy "and c".
    raw = "if a<b and c>d then x TAIL"
    out = safe_streszczenie_html(raw)
    assert "<b>" not in out
    assert "and c" in out
    assert "TAIL" in out


def test_safe_streszczenie_html_strips_jats_keeping_text():
    raw = "<jats:title>Abstract</jats:title><jats:p>BACKGROUND: disease.</jats:p>"
    out = safe_streszczenie_html(raw)
    assert "jats:" not in out
    assert "Abstract" in out
    assert "BACKGROUND: disease." in out


def test_safe_streszczenie_html_keeps_real_sup_sub():
    raw = "area 30<sup>th</sup> percentile CD4<sup>+</sup> H<sub>2</sub>O"
    out = safe_streszczenie_html(raw)
    assert "<sup>th</sup>" in out
    assert "<sub>2</sub>" in out


def test_safe_streszczenie_html_strips_xss():
    raw = "Hi <script>alert(1)</script> <img src=x onerror=alert(2)> bye"
    out = safe_streszczenie_html(raw)
    assert "script" not in out
    assert "onerror" not in out
    assert "bye" in out


@pytest.mark.parametrize("value", ["", None])
def test_safe_streszczenie_html_empty(value):
    assert safe_streszczenie_html(value) == ""


@pytest.mark.parametrize(
    "i, o",
    [
        (
            "identyfikacja markerów molekularnych",
            ["identyfikacja", "markerów", "molekularnych"],
        )
    ],
)
def test_fulltext_tokenize(i, o):
    assert fulltext_tokenize(i) == o
