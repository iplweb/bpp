import re

import bibtexparser

from . import (
    DataProvider,
    FetchedPublication,
    InputMode,
    register_provider,
)

# Mapowanie typów BibTeX → CrossRef (dla Komparator.porownaj_type)
BIBTEX_TYPE_MAP = {
    "article": "journal-article",
    "book": "book",
    "inbook": "book-chapter",
    "incollection": "book-chapter",
    "inproceedings": "proceedings-article",
    "conference": "proceedings-article",
    "phdthesis": "dissertation",
    "mastersthesis": "dissertation",
    "proceedings": "proceedings",
    "techreport": "report",
    "manual": "monograph",
    "misc": "other",
    "unpublished": "other",
}


@register_provider
class BibTeXProvider(DataProvider):
    @property
    def name(self) -> str:
        return "BibTeX"

    @property
    def identifier_label(self) -> str:
        return "Kod BibTeX"

    @property
    def input_mode(self) -> str:
        return InputMode.TEXT

    @property
    def input_placeholder(self) -> str:
        return (
            "@article{key,\n"
            "  title = {Tytuł publikacji},\n"
            "  author = {Nazwisko, Imię},\n"
            "  year = {2024},\n"
            "  ...\n"
            "}"
        )

    @property
    def input_help_text(self) -> str:
        return (
            "Wklej kod BibTeX publikacji. "
            "Jeśli podasz wiele wpisów, "
            "zostanie użyty pierwszy."
        )

    def validate_identifier(self, identifier: str) -> str | None:
        if not identifier or not identifier.strip():
            return None
        try:
            library = bibtexparser.parse_string(identifier)
        except Exception:
            return None
        if not library.entries:
            return None
        return identifier.strip()

    def fetch(self, identifier: str) -> FetchedPublication | None:
        try:
            library = bibtexparser.parse_string(identifier)
        except Exception:
            return None
        if not library.entries:
            return None

        entry = library.entries[0]
        fields = entry.fields_dict

        title = _get_field(fields, "title", "")
        if not title:
            return None

        authors = _parse_authors(_get_field(fields, "author", ""))
        year = _parse_year(_get_field(fields, "year", ""))
        doi = _clean_doi(_get_field(fields, "doi", ""))
        pages = _clean_pages(_get_field(fields, "pages", ""))

        keywords_raw = _get_field(fields, "keywords", "")
        keywords = (
            [k.strip() for k in keywords_raw.split(",") if k.strip()]
            if keywords_raw
            else []
        )

        bibtex_type = entry.entry_type.lower()
        publication_type = BIBTEX_TYPE_MAP.get(bibtex_type)

        raw_data = {
            "bibtex_text": identifier,
            "bibtex_type": bibtex_type,
            "bibtex_key": entry.key,
        }

        return FetchedPublication(
            raw_data=raw_data,
            title=title,
            doi=doi or None,
            year=year,
            authors=authors,
            source_title=(
                _get_field(fields, "journal", "")
                or _get_field(fields, "booktitle", "")
                or None
            ),
            issn=_get_field(fields, "issn", "") or None,
            isbn=_get_field(fields, "isbn", "") or None,
            publisher=_get_field(fields, "publisher", "") or None,
            publication_type=publication_type,
            language=_get_field(fields, "language", "") or None,
            abstract=_get_field(fields, "abstract", "") or None,
            volume=_get_field(fields, "volume", "") or None,
            issue=_get_field(fields, "number", "") or None,
            pages=pages or None,
            url=_get_field(fields, "url", "") or None,
            keywords=keywords,
            extra={"bibtex_key": entry.key},
        )


def _get_field(fields_dict, key, default=""):
    """Bezpiecznie pobierz wartość pola BibTeX."""
    field_obj = fields_dict.get(key)
    if field_obj is None:
        return default
    return str(field_obj.value).strip()


def _parse_authors(author_str: str) -> list[dict]:
    """Parsuj string autorów BibTeX na listę dict."""
    if not author_str:
        return []

    authors = []
    for part in author_str.split(" and "):
        part = part.strip()
        if not part:
            continue

        part = _clean_latex(part)

        if "," in part:
            # Format "Nazwisko, Imię"
            pieces = part.split(",", 1)
            family = pieces[0].strip()
            given = pieces[1].strip() if len(pieces) > 1 else ""
        else:
            # Format "Imię Nazwisko"
            pieces = part.rsplit(None, 1)
            if len(pieces) == 2:
                given = pieces[0].strip()
                family = pieces[1].strip()
            else:
                family = pieces[0].strip()
                given = ""

        authors.append({"family": family, "given": given})

    return authors


def _clean_latex(text: str) -> str:
    """Usuń proste polecenia LaTeX z tekstu."""
    # Usuń klamry
    text = text.replace("{", "").replace("}", "")
    # Usuń \~ \' \" itp.
    text = re.sub(r"\\[`'^\"~=.uvHtcdbr]", "", text)
    # Usuń \command z jednym argumentem
    text = re.sub(r"\\[a-zA-Z]+\s*", "", text)
    return text.strip()


def _parse_year(year_str: str) -> int | None:
    """Wyciągnij rok z pola year."""
    if not year_str:
        return None
    match = re.search(r"\d{4}", year_str)
    if match:
        return int(match.group())
    return None


def _clean_doi(doi_str: str) -> str:
    """Wyczyść DOI z prefiksu URL."""
    if not doi_str:
        return ""
    doi_str = doi_str.strip()
    for prefix in [
        "https://doi.org/",
        "http://doi.org/",
        "https://dx.doi.org/",
        "http://dx.doi.org/",
    ]:
        if doi_str.lower().startswith(prefix.lower()):
            return doi_str[len(prefix) :]
    return doi_str


def _clean_pages(pages_str: str) -> str:
    """Zamień '--' na '-' w stronach."""
    if not pages_str:
        return ""
    return pages_str.replace("--", "-")
