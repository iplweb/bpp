"""Pakiet ``importer_publikacji.views`` — re-eksport publicznego API.

Plik ``views.py`` rozrósł się ponad próg utrzymywalności, więc kod został
podzielony na cztery pod-moduły wg odpowiedzialności:

* :mod:`.helpers`       — stałe, ścieżki szablonów, drobne pomocnicze
                          funkcje (HTMX, breadcrumbs, kontekst fetch / lista
                          sesji, wykrywanie języka, mapowanie typu CrossRef);
* :mod:`.pbn_check`     — sprawdzenie publikacji w PBN po DOI + linkowanie
                          ``pbn_uid`` do utworzonego rekordu;
* :mod:`.authors`       — auto-matching autorów, prefill dyscyplin ze
                          zgłoszeń, tworzenie brakujących Autor-ów;
* :mod:`.steps`         — buildery kontekstu i renderery kroków wizarda
                          (verify / source / authors / review);
* :mod:`.publikacja`    — tworzenie końcowego rekordu publikacji
                          (Wydawnictwo_Ciagle / Wydawnictwo_Zwarte) wraz
                          z autorami i streszczeniami;
* :mod:`.wizard`        — class-based views urls.py (Index, Fetch, Verify,
                          Source, Authors, Review, Create, Done, Cancel,
                          AuthorMatch, …).

Symbole prywatne (z prefixem ``_``) są re-eksportowane, bo używają ich
istniejące testy (``importer_publikacji.tests.*``) i tylko w ten sposób
da się utrzymać kompatybilność wsteczną z patchami w mockach
(``unittest.mock.patch("importer_publikacji.views._<name>")``).
"""

import logging

from .authors import (
    _auto_match_authors,
    _create_unmatched_authors,
    _find_matching_zgloszenie,
    _get_dyscyplina,
    _orcid_settable_qs,
    _prefill_dyscypliny_z_zgloszen,
)
from .helpers import (
    BREADCRUMBS_OOB,
    INDEX,
    SESSIONS_ALLOWED_SORTS,
    SESSIONS_PARTIAL,
    STEP_AUTHORS,
    STEP_DONE,
    STEP_FETCH,
    STEP_REVIEW,
    STEP_SOURCE,
    STEP_VERIFY,
    _detect_language,
    _fetch_context,
    _get_crossref_mapper,
    _push_url,
    _render_full_page,
    _sessions_list_context,
    _sessions_queryset,
    _with_breadcrumbs_oob,
)
from .pbn_check import (
    _check_pbn_by_doi,
    _empty_pbn_result,
    _ensure_pbn_publication_local,
    _get_pbn_publication_by_doi,
    _link_pbn_uid,
    _populate_pbn_result,
)
from .publikacja import (
    _add_authors_to_record,
    _build_abstracts_list,
    _create_publication,
    _create_streszczenia,
    _create_wydawnictwo_ciagle,
    _create_wydawnictwo_zwarte,
    _resolve_jezyk,
)
from .steps import (
    _authors_context,
    _find_duplicates,
    _is_chapter,
    _is_crossref_data,
    _render_authors_full,
    _render_authors_step,
    _render_review_full,
    _render_review_step,
    _render_source_full,
    _render_source_step,
    _render_verify_full,
    _render_verify_step,
    _review_context,
    _source_context,
    _source_initial_auto_match,
    _source_initial_from_session,
    _verify_context,
)
from .wizard import (
    AuthorCandidatesModalView,
    AuthorCreateNewView,
    AuthorInfoView,
    AuthorMatchView,
    AuthorsConfirmView,
    AuthorSetOrcidView,
    AuthorsSetOrcidsView,
    AuthorsView,
    CancelView,
    CreateUnmatchedAuthorsView,
    CreateView,
    DoneView,
    FetchView,
    IndexView,
    ReviewView,
    SessionListView,
    SourceView,
    VerifyView,
)

# logger wystawiony na poziomie pakietu — zachowuje zgodność z poprzednim
# układem ``views.py`` (pojedynczy plik); część kodu może patchować go
# bezpośrednio przez ``importer_publikacji.views.logger``.
logger = logging.getLogger(__name__)

__all__ = [
    # Stałe
    "BREADCRUMBS_OOB",
    "INDEX",
    "SESSIONS_ALLOWED_SORTS",
    "SESSIONS_PARTIAL",
    "STEP_AUTHORS",
    "STEP_DONE",
    "STEP_FETCH",
    "STEP_REVIEW",
    "STEP_SOURCE",
    "STEP_VERIFY",
    # Class-based views
    "AuthorCandidatesModalView",
    "AuthorCreateNewView",
    "AuthorInfoView",
    "AuthorMatchView",
    "AuthorSetOrcidView",
    "AuthorsConfirmView",
    "AuthorsSetOrcidsView",
    "AuthorsView",
    "CancelView",
    "CreateUnmatchedAuthorsView",
    "CreateView",
    "DoneView",
    "FetchView",
    "IndexView",
    "ReviewView",
    "SessionListView",
    "SourceView",
    "VerifyView",
    # Funkcje (pakiet wystawia je z prefixem _ — patrz docstring modułu)
    "_add_authors_to_record",
    "_auto_match_authors",
    "_authors_context",
    "_build_abstracts_list",
    "_check_pbn_by_doi",
    "_create_publication",
    "_create_streszczenia",
    "_create_unmatched_authors",
    "_create_wydawnictwo_ciagle",
    "_create_wydawnictwo_zwarte",
    "_detect_language",
    "_empty_pbn_result",
    "_ensure_pbn_publication_local",
    "_fetch_context",
    "_find_duplicates",
    "_find_matching_zgloszenie",
    "_get_crossref_mapper",
    "_get_dyscyplina",
    "_get_pbn_publication_by_doi",
    "_is_chapter",
    "_is_crossref_data",
    "_link_pbn_uid",
    "_orcid_settable_qs",
    "_populate_pbn_result",
    "_prefill_dyscypliny_z_zgloszen",
    "_push_url",
    "_render_authors_full",
    "_render_authors_step",
    "_render_full_page",
    "_render_review_full",
    "_render_review_step",
    "_render_source_full",
    "_render_source_step",
    "_render_verify_full",
    "_render_verify_step",
    "_resolve_jezyk",
    "_review_context",
    "_sessions_list_context",
    "_sessions_queryset",
    "_source_context",
    "_source_initial_auto_match",
    "_source_initial_from_session",
    "_verify_context",
    "_with_breadcrumbs_oob",
    "logger",
]
