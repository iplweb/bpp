from importer_publikacji.providers import (
    InputMode,
    get_available_providers,
    get_provider,
    get_providers_metadata,
)
from importer_publikacji.providers.bibtex import (
    BibTeXProvider,
    _clean_doi,
    _clean_pages,
    _parse_authors,
    _parse_year,
)

SAMPLE_ARTICLE = """
@article{kowalski2024,
  title = {Some Important Research},
  author = {Kowalski, Jan and Nowak, Anna Maria},
  journal = {Journal of Testing},
  year = {2024},
  volume = {42},
  number = {3},
  pages = {100--115},
  doi = {10.1234/test.2024},
  issn = {1234-5678},
  language = {en},
  keywords = {testing, science, research},
  abstract = {This is an abstract.},
  url = {https://example.com/article},
}
"""

SAMPLE_BOOK = """
@book{nowak2023,
  title = {A Great Book},
  author = {Nowak, Piotr},
  publisher = {Academic Press},
  year = {2023},
  isbn = {978-3-16-148410-0},
}
"""

SAMPLE_INPROCEEDINGS = """
@inproceedings{smith2024,
  title = {Conference Paper Title},
  author = {Smith, John and Doe, Jane},
  booktitle = {Proceedings of the Conf},
  year = {2024},
}
"""


def test_bibtex_provider_registered():
    providers = get_available_providers()
    assert "BibTeX" in providers


def test_bibtex_provider_name():
    p = BibTeXProvider()
    assert p.name == "BibTeX"
    assert p.identifier_label == "Kod BibTeX"


def test_bibtex_provider_input_mode():
    p = BibTeXProvider()
    assert p.input_mode == InputMode.TEXT


def test_bibtex_provider_metadata():
    meta = get_providers_metadata()
    assert "BibTeX" in meta
    assert meta["BibTeX"]["input_mode"] == "text"


def test_get_provider_bibtex():
    p = get_provider("BibTeX")
    assert isinstance(p, BibTeXProvider)


# --- validate_identifier ---


def test_validate_valid_bibtex():
    p = BibTeXProvider()
    result = p.validate_identifier(SAMPLE_ARTICLE)
    assert result is not None


def test_validate_garbage():
    p = BibTeXProvider()
    result = p.validate_identifier("this is not bibtex")
    assert result is None


def test_validate_empty():
    p = BibTeXProvider()
    assert p.validate_identifier("") is None
    assert p.validate_identifier("   ") is None


# --- fetch: article ---


def test_fetch_article_basic_fields():
    p = BibTeXProvider()
    pub = p.fetch(SAMPLE_ARTICLE)
    assert pub is not None
    assert pub.title == "Some Important Research"
    assert pub.year == 2024
    assert pub.doi == "10.1234/test.2024"
    assert pub.volume == "42"
    assert pub.issue == "3"
    assert pub.pages == "100-115"
    assert pub.source_title == "Journal of Testing"
    assert pub.issn == "1234-5678"
    assert pub.language == "en"
    assert pub.abstract == "This is an abstract."
    assert pub.url == "https://example.com/article"


def test_fetch_article_authors():
    p = BibTeXProvider()
    pub = p.fetch(SAMPLE_ARTICLE)
    assert len(pub.authors) == 2
    assert pub.authors[0]["family"] == "Kowalski"
    assert pub.authors[0]["given"] == "Jan"
    assert pub.authors[1]["family"] == "Nowak"
    assert pub.authors[1]["given"] == "Anna Maria"


def test_fetch_article_keywords():
    p = BibTeXProvider()
    pub = p.fetch(SAMPLE_ARTICLE)
    assert pub.keywords == [
        "testing",
        "science",
        "research",
    ]


def test_fetch_article_type():
    p = BibTeXProvider()
    pub = p.fetch(SAMPLE_ARTICLE)
    assert pub.publication_type == "journal-article"


def test_fetch_article_raw_data():
    p = BibTeXProvider()
    pub = p.fetch(SAMPLE_ARTICLE)
    assert pub.raw_data["bibtex_type"] == "article"
    assert pub.raw_data["bibtex_key"] == "kowalski2024"
    assert "bibtex_text" in pub.raw_data


def test_fetch_article_extra():
    p = BibTeXProvider()
    pub = p.fetch(SAMPLE_ARTICLE)
    assert pub.extra["bibtex_key"] == "kowalski2024"


# --- fetch: book ---


def test_fetch_book():
    p = BibTeXProvider()
    pub = p.fetch(SAMPLE_BOOK)
    assert pub is not None
    assert pub.title == "A Great Book"
    assert pub.publisher == "Academic Press"
    assert pub.isbn == "978-3-16-148410-0"
    assert pub.publication_type == "book"
    assert pub.year == 2023
    assert len(pub.authors) == 1
    assert pub.authors[0]["family"] == "Nowak"


# --- fetch: inproceedings ---


def test_fetch_inproceedings():
    p = BibTeXProvider()
    pub = p.fetch(SAMPLE_INPROCEEDINGS)
    assert pub is not None
    assert pub.publication_type == "proceedings-article"
    assert pub.source_title == "Proceedings of the Conf"


# --- fetch: multiple entries → first ---


def test_fetch_multiple_entries_takes_first():
    bibtex = SAMPLE_ARTICLE + "\n" + SAMPLE_BOOK
    p = BibTeXProvider()
    pub = p.fetch(bibtex)
    assert pub is not None
    assert pub.title == "Some Important Research"


# --- fetch: no title → None ---


def test_fetch_no_title_returns_none():
    bibtex = """
@article{test,
  author = {Smith, John},
  year = {2024},
}
"""
    p = BibTeXProvider()
    assert p.fetch(bibtex) is None


# --- fetch: garbage → None ---


def test_fetch_garbage_returns_none():
    p = BibTeXProvider()
    assert p.fetch("not bibtex at all") is None


# --- author parsing ---


def test_parse_authors_last_first():
    result = _parse_authors("Kowalski, Jan and Nowak, Anna")
    assert len(result) == 2
    assert result[0] == {
        "family": "Kowalski",
        "given": "Jan",
    }
    assert result[1] == {
        "family": "Nowak",
        "given": "Anna",
    }


def test_parse_authors_first_last():
    result = _parse_authors("Jan Kowalski and Anna Nowak")
    assert len(result) == 2
    assert result[0] == {
        "family": "Kowalski",
        "given": "Jan",
    }
    assert result[1] == {
        "family": "Nowak",
        "given": "Anna",
    }


def test_parse_authors_single():
    result = _parse_authors("Kowalski, Jan")
    assert len(result) == 1
    assert result[0]["family"] == "Kowalski"
    assert result[0]["given"] == "Jan"


def test_parse_authors_empty():
    assert _parse_authors("") == []


# --- DOI cleaning ---


def test_clean_doi_url_prefix():
    assert _clean_doi("https://doi.org/10.1234/test") == "10.1234/test"
    assert _clean_doi("http://doi.org/10.1234/test") == "10.1234/test"
    assert _clean_doi("https://dx.doi.org/10.1234/test") == "10.1234/test"


def test_clean_doi_plain():
    assert _clean_doi("10.1234/test") == "10.1234/test"


def test_clean_doi_empty():
    assert _clean_doi("") == ""


# --- pages cleaning ---


def test_clean_pages_double_dash():
    assert _clean_pages("100--115") == "100-115"


def test_clean_pages_single_dash():
    assert _clean_pages("100-115") == "100-115"


def test_clean_pages_empty():
    assert _clean_pages("") == ""


# --- year parsing ---


def test_parse_year_simple():
    assert _parse_year("2024") == 2024


def test_parse_year_with_text():
    assert _parse_year("circa 2024") == 2024


def test_parse_year_empty():
    assert _parse_year("") is None


# --- type mapping ---


def test_type_mapping_article():
    p = BibTeXProvider()
    pub = p.fetch(SAMPLE_ARTICLE)
    assert pub.publication_type == "journal-article"


def test_type_mapping_thesis():
    bibtex = """
@phdthesis{thesis2024,
  title = {My PhD Thesis},
  author = {Kowalski, Jan},
  year = {2024},
  school = {University},
}
"""
    p = BibTeXProvider()
    pub = p.fetch(bibtex)
    assert pub is not None
    assert pub.publication_type == "dissertation"


def test_type_mapping_incollection():
    bibtex = """
@incollection{chapter2024,
  title = {A Chapter Title},
  author = {Smith, John},
  booktitle = {The Big Book},
  publisher = {Publisher},
  year = {2024},
}
"""
    p = BibTeXProvider()
    pub = p.fetch(bibtex)
    assert pub is not None
    assert pub.publication_type == "book-chapter"
    assert pub.source_title == "The Big Book"


def test_type_mapping_unknown():
    bibtex = """
@webpage{web2024,
  title = {Some Webpage},
  author = {Anonymous},
  year = {2024},
}
"""
    p = BibTeXProvider()
    pub = p.fetch(bibtex)
    assert pub is not None
    assert pub.publication_type is None
