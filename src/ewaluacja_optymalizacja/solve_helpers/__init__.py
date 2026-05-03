"""Helpers for the ``solve_evaluation`` management command.

Each submodule contains module-level functions extracted from the original
monolithic command. Functions take a ``stdout`` writer and a ``style``
helper (both supplied by ``BaseCommand``) so they can produce styled
output without owning the command instance.
"""

from .capacity_unpinning import handle_capacity_based_unpinning
from .display import (
    display_author_results,
    display_institution_statistics,
    find_unselected_multi_author_pubs,
)
from .json_export import save_results_to_json_file
from .persistence import (
    load_author_names_and_records,
    save_optimization_to_database,
)
from .phase3_pinning import handle_phase3_pinning
from .unpinning import handle_unpinning

__all__ = [
    "handle_capacity_based_unpinning",
    "display_author_results",
    "display_institution_statistics",
    "find_unselected_multi_author_pubs",
    "save_results_to_json_file",
    "load_author_names_and_records",
    "save_optimization_to_database",
    "handle_phase3_pinning",
    "handle_unpinning",
]
