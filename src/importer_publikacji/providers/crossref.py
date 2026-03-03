from crossref_bpp.models import CrossrefAPICache
from import_common.normalization import normalize_doi

from . import DataProvider, FetchedPublication, register_provider


@register_provider
class CrossRefProvider(DataProvider):
    @property
    def name(self) -> str:
        return "CrossRef"

    @property
    def identifier_label(self) -> str:
        return "Identyfikator DOI"

    def validate_identifier(self, identifier: str) -> str | None:
        return normalize_doi(identifier)

    def fetch(self, identifier: str) -> FetchedPublication | None:
        doi = self.validate_identifier(identifier)
        if doi is None:
            return None

        data = CrossrefAPICache.objects.get_by_doi(doi)
        if data is None:
            return None

        title = data.get("title", [])
        if isinstance(title, list):
            title = ". ".join(title) if title else ""

        authors = []
        for author in data.get("author", []):
            authors.append(
                {
                    "family": author.get("family", ""),
                    "given": author.get("given", ""),
                    "orcid": _extract_orcid(author.get("ORCID", "")),
                }
            )

        container_title = data.get("container-title", [])
        source_title = container_title[0] if container_title else None

        short_container = data.get("short-container-title", [])
        source_abbr = short_container[0] if short_container else None

        issn, e_issn = _extract_issn(data)
        isbn, e_isbn = _extract_isbn(data)

        year = data.get("published", {}).get("date-parts", [[None]])[0][0]

        license_url = None
        for lic in data.get("license", []):
            url = lic.get("URL")
            if url:
                license_url = url
                break

        extra = _build_extra(data, title)

        return FetchedPublication(
            raw_data=data,
            title=title,
            doi=data.get("DOI"),
            year=year,
            authors=authors,
            source_title=source_title,
            source_abbreviation=source_abbr,
            issn=issn,
            e_issn=e_issn,
            isbn=isbn,
            e_isbn=e_isbn,
            publisher=data.get("publisher"),
            publication_type=data.get("type"),
            language=data.get("language"),
            abstract=data.get("abstract"),
            volume=data.get("volume"),
            issue=data.get("issue"),
            pages=data.get("page"),
            url=(data.get("resource", {}).get("primary", {}).get("URL")),
            license_url=license_url,
            keywords=data.get("subject", []),
            extra=extra,
        )


def _build_extra(data: dict, title: str) -> dict:
    """Zbuduj slownik z dodatkowymi polami z danych CrossRef."""
    extra = {}

    article_number = data.get("article-number")
    if article_number:
        extra["article_number"] = article_number

    original_title = data.get("original-title", [])
    if isinstance(original_title, list) and original_title:
        original_title = ". ".join(original_title)
    elif isinstance(original_title, list):
        original_title = None
    if original_title and original_title != title:
        extra["original_title"] = original_title

    return extra


def _extract_orcid(orcid_url: str) -> str:
    """Wyciągnij ORCID z URL lub zwróć jak jest."""
    if not orcid_url:
        return ""
    orcid_url = orcid_url.strip()
    for prefix in [
        "https://orcid.org/",
        "http://orcid.org/",
    ]:
        if orcid_url.lower().startswith(prefix.lower()):
            return orcid_url[len(prefix) :]
    return orcid_url


def _extract_issn(data: dict) -> tuple[str | None, str | None]:
    issn = None
    e_issn = None
    for item in data.get("issn-type", []):
        if item.get("type") == "electronic":
            e_issn = item.get("value")
        else:
            issn = item.get("value")

    if issn is None and data.get("ISSN"):
        try:
            issn = data["ISSN"][0]
        except IndexError:
            pass
        if issn and issn == e_issn:
            issn = None

    return issn, e_issn


def _extract_isbn(data: dict) -> tuple[str | None, str | None]:
    isbn = None
    e_isbn = None
    for item in data.get("isbn-type", []):
        if item.get("type") == "electronic":
            e_isbn = item.get("value")
        else:
            isbn = item.get("value")

    if isbn is None and data.get("ISBN"):
        try:
            isbn = data["ISBN"][0]
        except IndexError:
            pass
        if isbn and isbn == e_isbn:
            isbn = None

    return isbn, e_isbn
