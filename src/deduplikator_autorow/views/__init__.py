"""Public view interface for the ``deduplikator_autorow`` app.

This package was split out of a single ``views.py`` module. All previously
public symbols are re-exported here so existing imports (urls.py, tests, etc.)
continue to work via ``from deduplikator_autorow.views import ...``.

Module map:
- :mod:`.helpers` — decorators, session helpers, candidate/scan query helpers,
  param resolution helpers
- :mod:`.duplicates` — main duplicate-browsing/resolution views and lastname
  autocomplete
- :mod:`.merge` — merge & delete-author views
- :mod:`.ignore` — ignored-author management views (PBN + BPP)
- :mod:`.scan` — scan-task lifecycle (start/cancel/status) views
- :mod:`.export` — XLSX export view
"""

from .duplicates import (
    duplicate_authors_view,
    lastname_suggestions,
    mark_candidate_not_duplicate,
    mark_non_duplicate,
    reset_not_duplicates,
    reset_skipped_authors,
)
from .export import download_duplicates_xlsx
from .helpers import (
    MIN_PEWNOSC_DO_WYSWIETLENIA,
    _add_dyscypliny_to_duplicates,
    _build_context_from_candidate,
    _build_duplicate_publication_data,
    _calculate_year_range,
    _clear_navigation_session,
    _get_excluded_authors_from_session,
    _get_next_candidate_group,
    _get_pending_candidates_for_main_autor,
    _handle_go_previous,
    _handle_search_request,
    _handle_skip_current,
    _read_param,
    _resolve_autor_id,
    _scientist_id_to_autor_id,
    get_running_scan,
    group_required,
)
from .ignore import (
    _trigger_rescan_after_reset,
    ignore_autor,
    ignore_scientist,
    reset_ignored_autorzy,
    reset_ignored_scientists,
)
from .merge import delete_author, scal_autorow_view
from .scan import cancel_scan_view, scan_status_view, start_scan_view

__all__ = [
    "MIN_PEWNOSC_DO_WYSWIETLENIA",
    "_add_dyscypliny_to_duplicates",
    "_build_context_from_candidate",
    "_build_duplicate_publication_data",
    "_calculate_year_range",
    "_clear_navigation_session",
    "_get_excluded_authors_from_session",
    "_get_next_candidate_group",
    "_get_pending_candidates_for_main_autor",
    "_handle_go_previous",
    "_handle_search_request",
    "_handle_skip_current",
    "_read_param",
    "_resolve_autor_id",
    "_scientist_id_to_autor_id",
    "_trigger_rescan_after_reset",
    "cancel_scan_view",
    "delete_author",
    "download_duplicates_xlsx",
    "duplicate_authors_view",
    "get_running_scan",
    "group_required",
    "ignore_autor",
    "ignore_scientist",
    "lastname_suggestions",
    "mark_candidate_not_duplicate",
    "mark_non_duplicate",
    "reset_ignored_autorzy",
    "reset_ignored_scientists",
    "reset_not_duplicates",
    "reset_skipped_authors",
    "scal_autorow_view",
    "scan_status_view",
    "start_scan_view",
]
