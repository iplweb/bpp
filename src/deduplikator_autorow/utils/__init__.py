"""
Moduł do wyszukiwania zdublowanych autorów w systemie BPP.

This package provides utilities for finding and managing duplicate authors.
All functions are re-exported here for backwards compatibility.
"""

from .analysis import analiza_duplikatow, autor_ma_publikacje_z_lat
from .constants import MAX_PEWNOSC, MIN_PEWNOSC
from .counters import count_authors_with_duplicates, count_authors_with_lastname
from .export import export_duplicates_to_xlsx
from .finders import search_author_by_lastname, znajdz_pierwszego_autora_z_duplikatami
from .merge import scal_autora, scal_autorow
from .search import szukaj_kopii

__all__ = [
    # Constants
    "MAX_PEWNOSC",
    "MIN_PEWNOSC",
    # Search
    "szukaj_kopii",
    # Analysis
    "analiza_duplikatow",
    "autor_ma_publikacje_z_lat",
    # Finders
    "znajdz_pierwszego_autora_z_duplikatami",
    "search_author_by_lastname",
    # Merge
    "scal_autora",
    "scal_autorow",
    # Counters
    "count_authors_with_duplicates",
    "count_authors_with_lastname",
    # Export
    "export_duplicates_to_xlsx",
]
