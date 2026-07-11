import logging
import re

import bibtexparser
from bibtexparser.model import Entry, ParsingFailedBlock

from bpp.util import zaloguj_polkniety_wyjatek

from . import (
    DataProvider,
    FetchedPublication,
    InputMode,
    SplitRecord,
    register_provider,
)

logger = logging.getLogger(__name__)

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
    # "patent" nie jest typem CrossRef — nie ma odpowiednika w
    # Crossref_Mapper.CHARAKTER_CROSSREF (brak wpisu = _get_crossref_mapper
    # bezpiecznie zwraca None, bez auto-podpowiedzi charakteru formalnego,
    # co jest poprawne: patenty tworzą osobny model bpp.Patent, nie
    # Wydawnictwo_Ciagle/Zwarte). Wartość jest markerem rozpoznawanym w
    # dalszym potoku importera (normalized_data["publication_type"]).
    "patent": "patent",
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
            "Wklej kod BibTeX. Możesz wkleić wiele wpisów naraz — "
            "każdy trafi do osobnej pozycji na liście do zaimportowania."
        )

    def validate_identifier(self, identifier: str) -> str | None:
        if not identifier or not identifier.strip():
            return None
        try:
            library = bibtexparser.parse_string(identifier)
        except Exception:
            zaloguj_polkniety_wyjatek(
                "Walidacja identyfikatora BibTeX (bibtexparser)",
                logger=logger,
            )
            return None
        if not library.entries:
            return None
        return identifier.strip()

    def peek_title(self, entry) -> str:
        """Wyciągnij tytuł z wpisu do wyświetlenia (unwrap Field + LaTeX)."""
        title = _get_field(entry.fields_dict, "title", "")
        if not title:
            return ""
        return _clean_latex(title)

    def split_input(self, text: str) -> list[SplitRecord]:
        """Rozbij wklejony BibTeX na pojedyncze rekordy.

        Każdy poprawny wpis → jeden ``SplitRecord(ok=True)`` z ``entry.raw``
        (verbatim). Każdy uszkodzony blok (``failed_blocks``) → jeden
        ``SplitRecord(ok=False)`` niosący surowy tekst + komunikat — inaczej
        znikałby po cichu (dokładnie bug, który naprawiamy). Kolejność
        źródłowa zachowana przez iterację po ``library.blocks``.
        """
        library = bibtexparser.parse_string(text)
        records: list[SplitRecord] = []
        for block in library.blocks:
            if isinstance(block, Entry):
                records.append(
                    SplitRecord(raw=block.raw, ok=True, title=self.peek_title(block))
                )
            elif isinstance(block, ParsingFailedBlock):
                records.append(
                    SplitRecord(
                        raw=block.raw,
                        ok=False,
                        error="Nie udało się sparsować wpisu BibTeX.",
                    )
                )
        return records

    def fetch(self, identifier: str) -> FetchedPublication | None:
        # NIE lykamy po cichu: nieoczekiwany blad parsera to bug, ktory ma
        # trafic do logow + Rollbara (przez @task_failure w celery_tasks),
        # a nie zniknac jako "dostawca nic nie zwrocil". validate_identifier
        # juz potwierdzil parsowalnosc synchronicznie przed kolejka.
        try:
            library = bibtexparser.parse_string(identifier)
        except Exception:
            logger.exception("Nieoczekiwany blad parsowania BibTeX w fetch()")
            raise
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

        patent_number = patent_holder = jurisdiction = patent_type = None
        filing_date = None
        if bibtex_type == "patent":
            patent_number = _get_field(fields, "number", "") or None
            patent_holder = _clean_latex(_get_field(fields, "holder", "")) or None
            jurisdiction = _get_field(fields, "location", "") or None
            patent_type = _get_field(fields, "type", "") or None
            filing_date = _parse_bibtex_date(_get_field(fields, "date", ""))

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
            patent_number=patent_number,
            patent_holder=patent_holder,
            jurisdiction=jurisdiction,
            patent_type=patent_type,
            filing_date=filing_date,
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
    # Separator autorow w BibTeX to slowo "and" otoczone DOWOLNYM bialym
    # znakiem — w realnych wpisach (czasopisma, Zotero) lista autorow jest
    # zwykle lamana na wiele linii ("... and\n   Nastepny, Autor"), wiec
    # literalne split(" and ") nie trafia i wszyscy autorzy laduja w jednym
    # rekordzie (regresja Freshdesk #344). Dzielimy po \s+and\s+.
    for part in re.split(r"\s+and\s+", author_str):
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


def _parse_bibtex_date(date_str: str) -> str | None:
    """Wyciągnij pełną datę ISO (YYYY-MM-DD) z biblatex pola ``date``.

    Biblatex dopuszcza samo ``date = {2024}`` (sam rok) — wtedy nie ma z
    czego zbudować pełnej daty (``Patent.data_zgloszenia`` to ``DateField``),
    więc świadomie zwracamy ``None`` zamiast zgadywać miesiąc/dzień;
    operator uzupełnia datę ręcznie w wizardzie.
    """
    if not date_str:
        return None
    match = re.match(r"^(\d{4})-(\d{2})-(\d{2})", date_str.strip())
    if match:
        return match.group(0)
    return None


def _clean_pages(pages_str: str) -> str:
    """Znormalizuj separator zakresu stron do ASCII '-'.

    BibTeX zapisuje zakres jako '--' (en-dash) lub '---' (em-dash), ale
    wklejane wpisy czesto maja prawdziwe znaki unicode: en-dash '–', em-dash
    '—', minus '−', figure dash '‒', horizontal bar '―'. Wszystko sprowadzamy
    do '-', zeby ``Wydawnictwo_*.pierwsza_strona``/``ostatnia_strona``
    (split po '-') poprawnie rozbijaly zakres (Freshdesk #344: 'S180—S180').
    """
    if not pages_str:
        return ""
    for dash in ("–", "—", "−", "‒", "―"):
        pages_str = pages_str.replace(dash, "-")
    # '--' / '---' (LaTeX) oraz powtorzone '-' -> pojedynczy '-'.
    return re.sub(r"-{2,}", "-", pages_str)
