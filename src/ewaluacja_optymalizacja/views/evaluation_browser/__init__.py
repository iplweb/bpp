"""Pakiet widoków przeglądarki ewaluacji.

Podzielony z dawnego pliku ``evaluation_browser.py`` (851 linii) na:

- ``discipline_summary`` — podsumowanie dyscyplin + opcje filtrów,
- ``prefetch`` — batch pre-fetchery (autorzy, punktacja, sloty),
- ``filters`` — buildery filtrów na queryset publikacji,
- ``builders`` — składanie list publikacji/autorów dla widoków,
- ``views`` — widoki HTTP (HTMX partials, akcje pin/swap).

Wszystkie publiczne widoki używane w ``urls.py`` oraz "prywatne"
helpery używane przez testy (``tests/test_evaluation_browser_helpers.py``)
re-eksportujemy z tego ``__init__`` żeby zachować zgodność wsteczną
importów ``ewaluacja_optymalizacja.views.evaluation_browser.<symbol>``.
"""

from .builders import (
    _build_authors_list,
    _build_publication_list,
    _get_filtered_publications,
)
from .discipline_summary import (
    _get_discipline_summary,
    _get_filter_options,
    _get_reported_disciplines,
    _snapshot_discipline_points,
)
from .filters import (
    _apply_dyscyplina_nieprzypisana_filter,
    _build_author_filter,
    _build_base_filter,
)
from .prefetch import (
    _build_rekord_ids,
    _prefetch_autor_dyscypliny,
    _prefetch_autor_max_slots,
    _prefetch_autor_slot_nazbierany,
    _prefetch_autorzy_by_pub,
    _prefetch_punktacja_cache,
    _prefetch_selected_publications,
)
from .views import (
    browser_recalc_status,
    browser_summary,
    browser_swap_discipline,
    browser_table,
    browser_toggle_pin,
    evaluation_browser,
)

__all__ = [
    # Public views (used in urls.py)
    "evaluation_browser",
    "browser_summary",
    "browser_table",
    "browser_toggle_pin",
    "browser_swap_discipline",
    "browser_recalc_status",
    # Helpers re-exported for backward compatibility with tests
    "_get_reported_disciplines",
    "_snapshot_discipline_points",
    "_get_discipline_summary",
    "_get_filter_options",
    "_get_filtered_publications",
    "_build_authors_list",
    "_build_publication_list",
    "_apply_dyscyplina_nieprzypisana_filter",
    "_build_base_filter",
    "_build_author_filter",
    "_build_rekord_ids",
    "_prefetch_selected_publications",
    "_prefetch_punktacja_cache",
    "_prefetch_autorzy_by_pub",
    "_prefetch_autor_dyscypliny",
    "_prefetch_autor_max_slots",
    "_prefetch_autor_slot_nazbierany",
]
