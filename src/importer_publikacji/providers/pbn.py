import logging
import re

from pbn_api.exceptions import (
    AccessDeniedException,
    HttpException,
    PraceSerwisoweException,
)

from . import DataProvider, FetchedPublication, register_provider

logger = logging.getLogger(__name__)

_PBN_UID_RE = re.compile(r"^[0-9a-fA-F]{24}$")
_PBN_URL_RE = re.compile(r"/publication/view/([0-9a-fA-F]{24})(?:/|$)")

# PBN type → CrossRef-compatible type
PBN_TYPE_MAP = {
    "ARTICLE": "journal-article",
    "BOOK": "book",
    "EDITED_BOOK": "edited-book",
    "CHAPTER": "book-chapter",
}

# PBN Open Access license → URL
PBN_LICENSE_MAP = {
    "CC_BY": "https://creativecommons.org/licenses/by/4.0/",
    "CC_BY_SA": ("https://creativecommons.org/licenses/by-sa/4.0/"),
    "CC_BY_NC": ("https://creativecommons.org/licenses/by-nc/4.0/"),
    "CC_BY_NC_SA": ("https://creativecommons.org/licenses/by-nc-sa/4.0/"),
    "CC_BY_ND": ("https://creativecommons.org/licenses/by-nd/4.0/"),
    "CC_BY_NC_ND": ("https://creativecommons.org/licenses/by-nc-nd/4.0/"),
}


def _get_pbn_client():
    from bpp.models import Uczelnia
    from pbn_api.client import PBNClient
    from pbn_api.client.transport import RequestsTransport

    uczelnia = Uczelnia.objects.get_default()
    if not uczelnia or not all(
        [
            uczelnia.pbn_app_name,
            uczelnia.pbn_app_token,
        ]
    ):
        raise ValueError("Brak konfiguracji PBN")

    transport = RequestsTransport(
        uczelnia.pbn_app_name,
        uczelnia.pbn_app_token,
        uczelnia.pbn_api_root,
    )
    return PBNClient(transport)


def _extract_authors(obj: dict) -> list[dict]:
    """Wyciągnij autorów z PBN publication object.

    PBN get_publication_by_id returns authors as a dict:
        {pbn_uid: {lastName, name}, ...}
    FetchedPublication format: {family, given, orcid}
    """
    raw = obj.get("authors", {})
    authors = []
    if isinstance(raw, dict):
        for _pbn_uid, author in raw.items():
            authors.append(
                {
                    "family": author.get("lastName", ""),
                    "given": author.get("name", ""),
                    "orcid": "",
                }
            )
    elif isinstance(raw, list):
        for author in raw:
            if isinstance(author, dict):
                authors.append(
                    {
                        "family": author.get("lastName", ""),
                        "given": author.get(
                            "firstName",
                            author.get("name", ""),
                        ),
                        "orcid": "",
                    }
                )
    return authors


def _extract_keywords(obj: dict) -> list[str]:
    """Spłaszcz wielojęzyczny słownik keywords do listy."""
    keywords_dict = obj.get("keywords")
    if not keywords_dict or not isinstance(keywords_dict, dict):
        return []

    result = []
    for lang_keywords in keywords_dict.values():
        if isinstance(lang_keywords, list):
            result.extend(lang_keywords)
        elif isinstance(lang_keywords, str):
            result.append(lang_keywords)
    return result


def _extract_abstract(obj: dict) -> str | None:
    """Wyciągnij pierwszy abstrakt z wielojęzycznego dict."""
    abstracts = obj.get("abstracts")
    if not abstracts or not isinstance(abstracts, dict):
        return None

    for value in abstracts.values():
        if value:
            return value
    return None


def _extract_license_url(obj: dict) -> str | None:
    """Mapuj PBN openAccess.license na URL licencji."""
    open_access = obj.get("openAccess")
    if not open_access or not isinstance(open_access, dict):
        return None

    license_code = open_access.get("license")
    if not license_code:
        return None

    return PBN_LICENSE_MAP.get(license_code)


def _extract_year(obj: dict) -> int | None:
    """Wyciągnij rok - najpierw z obj.year, potem book.year."""
    year = obj.get("year")
    if year is not None:
        return int(year)

    book = obj.get("book")
    if book and book.get("year") is not None:
        return int(book["year"])

    return None


def _extract_isbn(obj: dict) -> str | None:
    """Wyciągnij ISBN z obj.isbn lub obj.book.isbn."""
    isbn = obj.get("isbn")
    if isbn:
        return isbn

    book = obj.get("book")
    if book:
        return book.get("isbn")

    return None


def _get_current_version_object(data: dict) -> dict | None:
    """Wyciągnij obiekt z bieżącej wersji publikacji PBN."""
    versions = data.get("versions", [])
    for version in versions:
        if version.get("current"):
            return version.get("object", {})
    return None


def _save_to_pbn_publication(pbn_uid: str, data: dict):
    """Zapisz dane do pbn_api.Publication."""
    from pbn_api.models import Publication
    from pbn_integrator.utils.mongodb_ops import zapisz_mongodb

    zapisz_mongodb(data, Publication)


@register_provider
class PBNProvider(DataProvider):
    @property
    def name(self) -> str:
        return "PBN"

    @property
    def identifier_label(self) -> str:
        return "PBN UID lub adres URL w repozytorium PBN"

    @property
    def input_placeholder(self) -> str:
        return (
            "np. 5e709189878c28a04737dc6f"
            " lub https://pbn.nauka.gov.pl/core/#/publication/view/..."
        )

    @property
    def input_help_text(self) -> str:
        return (
            "Podaj PBN UID publikacji (24-znakowy hex) lub wklej URL z pbn.nauka.gov.pl"
        )

    def validate_identifier(self, identifier: str) -> str | None:
        uid = identifier.strip()
        if _PBN_UID_RE.match(uid):
            return uid
        m = _PBN_URL_RE.search(uid)
        if m:
            return m.group(1)
        return None

    def fetch(self, identifier: str) -> FetchedPublication | None:
        uid = self.validate_identifier(identifier)
        if uid is None:
            return None

        try:
            client = _get_pbn_client()
        except ValueError:
            logger.warning("Brak konfiguracji PBN w Uczelnia")
            return None

        try:
            data = client.get_publication_by_id(uid)
        except HttpException as e:
            if e.status_code == 404:
                return None
            raise
        except PraceSerwisoweException:
            logger.warning(
                "PBN: prace serwisowe podczas pobierania publikacji %s",
                uid,
            )
            return None
        except AccessDeniedException:
            logger.warning("PBN: brak dostępu do publikacji %s", uid)
            return None

        if data is None:
            return None

        # Zapisz do lokalnej bazy PBN
        _save_to_pbn_publication(uid, data)

        obj = _get_current_version_object(data)
        if obj is None:
            return None

        journal = obj.get("journal") or {}

        return FetchedPublication(
            raw_data=data,
            title=obj.get("title", ""),
            doi=obj.get("doi"),
            year=_extract_year(obj),
            authors=_extract_authors(obj),
            source_title=journal.get("title"),
            issn=journal.get("issn"),
            e_issn=journal.get("eissn"),
            isbn=_extract_isbn(obj),
            publisher=journal.get("publisher"),
            publication_type=PBN_TYPE_MAP.get(obj.get("type", "")),
            language=obj.get("mainLanguage"),
            abstract=_extract_abstract(obj),
            volume=obj.get("volume"),
            issue=obj.get("issue"),
            pages=obj.get("pagesFromTo"),
            url=obj.get("publicUri"),
            license_url=_extract_license_url(obj),
            keywords=_extract_keywords(obj),
            extra={"pbn_uid": uid},
        )
