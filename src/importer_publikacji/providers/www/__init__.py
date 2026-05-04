"""Provider importu publikacji z generycznych stron WWW.

Pakiet jest split-em wcześniejszego pliku ``www.py`` na moduły
funkcjonalne:

- :mod:`.parsers` — atomowe parsery (DOI / rok / autor / meta).
- :mod:`.citation_meta` — Highwire-Press ``citation_*`` meta tagi.
- :mod:`.dublin_core` — Dublin Core ``DC.*``.
- :mod:`.schema_jsonld` — Schema.org JSON-LD osadzony w HTML.
- :mod:`.omega_psir` — REST JSON-LD Omega-PSIR.
- :mod:`.opengraph` — OpenGraph (fallback).
- :mod:`.body_abstracts` — streszczenia z body HTML.
- :mod:`.merge` — łączenie wyników wielu ekstraktorów.
- :mod:`.network` — pobieranie strony + walidacja URL.
- :mod:`.provider` — klasa ``WWWProvider``.

Re-eksport poniżej zachowuje pełne wsteczne API: wszystkie nazwy
używane przez testy (i inne moduły kodu) są dostępne pod ścieżką
``importer_publikacji.providers.www.*`` tak jak przed splitem.

Uwaga dla testów: ``@patch("importer_publikacji.providers.www.requests.get")``
działa, bo ``requests`` jest tu re-eksportowany jako atrybut pakietu —
a sam moduł ``requests`` jest singletonem, więc patch dotyka również
``requests.get`` używanego w submodułach (network, omega_psir).
"""

import requests  # re-exported for `@patch("...www.requests.get")` compatibility

from .body_abstracts import (
    ABSTRACT_LABELS,
    MIN_ABSTRACT_LENGTH,
    _extract_body_abstracts,
    _get_abstract_content,
    _get_inline_tag_trailing_text,
    _get_th_content,
)
from .citation_meta import (
    _add_date_field,
    _add_keywords_field,
    _add_pages_field,
    _add_simple_fields,
    _extract_citation_meta,
)
from .dublin_core import (
    _extract_dc_doi,
    _extract_dc_simple_fields,
    _extract_dublin_core,
)
from .merge import _merge_sources
from .network import FETCH_TIMEOUT, _fetch_page, _validate_url
from .omega_psir import (
    OMEGA_ARTICLE_RE,
    _detect_omega_psir,
    _extract_omega_authors,
    _extract_omega_date,
    _extract_omega_doi,
    _extract_omega_journal_details,
    _extract_omega_journal_info,
    _extract_omega_language,
    _extract_omega_title,
    _fetch_omega_psir_jsonld,
    _find_omega_article,
    _parse_omega_jsonld,
)
from .opengraph import _extract_opengraph
from .parsers import (
    DOI_URL_PREFIXES,
    _clean_doi,
    _get_all_meta,
    _get_meta,
    _get_meta_property,
    _parse_author_name,
    _parse_year,
)
from .provider import (
    WWWProvider,
    _collect_citation_sources,
    _collect_fallback_sources,
    _collect_schema_sources,
)
from .schema_jsonld import (
    _extract_schema_authors,
    _extract_schema_date,
    _extract_schema_doi,
    _extract_schema_ispartof,
    _extract_schema_jsonld,
    _extract_schema_pages,
    _extract_schema_publisher,
    _extract_schema_title,
    _extract_schema_volume_issue,
    _process_schema_items,
)

__all__ = [
    "ABSTRACT_LABELS",
    "DOI_URL_PREFIXES",
    "FETCH_TIMEOUT",
    "MIN_ABSTRACT_LENGTH",
    "OMEGA_ARTICLE_RE",
    "WWWProvider",
    "_add_date_field",
    "_add_keywords_field",
    "_add_pages_field",
    "_add_simple_fields",
    "_clean_doi",
    "_collect_citation_sources",
    "_collect_fallback_sources",
    "_collect_schema_sources",
    "_detect_omega_psir",
    "_extract_body_abstracts",
    "_extract_citation_meta",
    "_extract_dc_doi",
    "_extract_dc_simple_fields",
    "_extract_dublin_core",
    "_extract_omega_authors",
    "_extract_omega_date",
    "_extract_omega_doi",
    "_extract_omega_journal_details",
    "_extract_omega_journal_info",
    "_extract_omega_language",
    "_extract_omega_title",
    "_extract_opengraph",
    "_extract_schema_authors",
    "_extract_schema_date",
    "_extract_schema_doi",
    "_extract_schema_ispartof",
    "_extract_schema_jsonld",
    "_extract_schema_pages",
    "_extract_schema_publisher",
    "_extract_schema_title",
    "_extract_schema_volume_issue",
    "_fetch_omega_psir_jsonld",
    "_fetch_page",
    "_find_omega_article",
    "_get_abstract_content",
    "_get_all_meta",
    "_get_inline_tag_trailing_text",
    "_get_meta",
    "_get_meta_property",
    "_get_th_content",
    "_merge_sources",
    "_parse_author_name",
    "_parse_omega_jsonld",
    "_parse_year",
    "_process_schema_items",
    "_validate_url",
    "requests",
]
