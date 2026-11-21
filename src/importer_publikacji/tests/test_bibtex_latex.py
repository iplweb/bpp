"""LaTeX -> Unicode cleanup of BibTeX text fields (Freshdesk #458)."""

import pytest

from importer_publikacji.providers.bibtex import BibTeXProvider, _clean_latex


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        # Braces protecting capitals (the client's example).
        ("{U}kraine", "Ukraine"),
        ("The war in {U}kraine", "The war in Ukraine"),
        ("{{Nested {Braces}}}", "Nested Braces"),
        # LaTeX quotes -> typographic quotes.
        ("``Quoted'' text", "“Quoted” text"),
        # Dashes.
        ("1990--2000", "1990–2000"),
        ("before --- after", "before — after"),
        ("well-known", "well-known"),
        # Polish diacritics.
        (r"{\k a}{\k e}", "ąę"),
        (r"{\l}{\L}", "łŁ"),
        (r"\'{n}\'{c}\'{s}\'{z}\'{o}", "ńćśźó"),
        (r"\.{z}\.{Z}", "żŻ"),
        (r"{\L}{\'o}d{\'z}", "Łódź"),
        (r"Pi{\'o}ro", "Pióro"),
        # Other accents.
        (r"Sch{\"o}n \"{u}ber", "Schön über"),
        (r"{\'a}\'{e}", "áé"),
        (r"\v{s}\c{c}{\ss}", "šçß"),
        # Formatting macros and escaped specials.
        (r"\textit{Homo sapiens} in vivo", "Homo sapiens in vivo"),
        (r"\emph{x}~y", "x y"),
        (r"50\% off \& more", "50% off & more"),
        # Unescaped % and & are plain characters in real exports.
        ("50% of patients", "50% of patients"),
        ("Smith & Jones", "Smith & Jones"),
        # Math stays intact.
        (r"Effect of $\alpha_{1}$ on $E=mc^2$", r"Effect of $\alpha_{1}$ on $E=mc^2$"),
        # Whitespace normalisation.
        ("  multi\n   line  ", "multi line"),
        ("", ""),
    ],
)
def test_clean_latex(raw, expected):
    assert _clean_latex(raw) == expected


@pytest.mark.parametrize(
    "text",
    [
        "Zażółć gęślą jaźń",
        "Plain English title: a study",
        "O'Brien and rock 'n' roll",
        "COVID-19 in 2020-2021",
    ],
)
def test_clean_latex_leaves_clean_text_unchanged(text):
    assert _clean_latex(text) == text


SAMPLE_LATEX_ARTICLE = r"""
@article{fd458,
  title = {The war in {U}kraine: ``hybrid'' threats, 2014--2022},
  author = {Pi{\'o}ro, {\L}ukasz and Sch{\"o}n, Ma{\l}gorzata and
            Ga{\l}{\k a}zka, Zbigniew},
  journal = {Bezpiecze{\'n}stwo {N}arodowe --- {S}tudia},
  publisher = {Wydawnictwo {A}kademii --- {\L}{\'o}d{\'z}},
  abstract = {We discuss ``{NATO}'' policy --- 50% of cases.},
  keywords = {{U}kraine, bezpiecze{\'n}stwo},
  year = {2024},
  pages = {100--115},
}
"""


def test_fetch_cleans_latex_in_text_fields():
    pub = BibTeXProvider().fetch(SAMPLE_LATEX_ARTICLE)
    assert pub is not None
    assert pub.title == "The war in Ukraine: “hybrid” threats, 2014–2022"
    assert pub.source_title == "Bezpieczeństwo Narodowe — Studia"
    assert pub.publisher == "Wydawnictwo Akademii — Łódź"
    assert pub.abstract == "We discuss “NATO” policy — 50% of cases."
    assert pub.keywords == ["Ukraine", "bezpieczeństwo"]
    assert pub.authors == [
        {"family": "Pióro", "given": "Łukasz"},
        {"family": "Schön", "given": "Małgorzata"},
        {"family": "Gałązka", "given": "Zbigniew"},
    ]
    # Pages keep the ASCII range separator used by the importer.
    assert pub.pages == "100-115"


def test_fetch_cleans_latex_in_booktitle():
    pub = BibTeXProvider().fetch(
        r"""
@inproceedings{x,
  title = {A {C}onference {P}aper},
  booktitle = {Proceedings of {IEEE} --- {\'E}cole},
  year = {2024},
}
"""
    )
    assert pub.title == "A Conference Paper"
    assert pub.source_title == "Proceedings of IEEE — École"


def test_split_input_title_matches_fetch_title():
    provider = BibTeXProvider()
    [record] = provider.split_input(SAMPLE_LATEX_ARTICLE)
    assert record.title == provider.fetch(record.raw).title


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("One line.", "One line."),
        ("First  line\n   second line", "First line\nsecond line"),
        ("Para one.\n\n\n\nPara two.", "Para one.\n\nPara two."),
        ("  \n{U}kraine ---\n\n  NATO~policy \n ", "Ukraine —\n\nNATO policy"),
    ],
)
def test_clean_latex_keep_lines(raw, expected):
    assert _clean_latex(raw, keep_lines=True) == expected


def test_fetch_abstract_keeps_line_breaks_other_fields_do_not():
    pub = BibTeXProvider().fetch(
        "@article{x,\n"
        "  title = {Wrapped\n           title},\n"
        "  abstract = {Background: {U}kraine.\n\n"
        "              Methods: ``survey''.\n"
        "              Results: 50% --- done.},\n"
        "  year = {2024},\n"
        "}\n"
    )
    assert pub.title == "Wrapped title"
    assert pub.abstract == (
        "Background: Ukraine.\n\nMethods: “survey”.\nResults: 50% — done."
    )
