"""Stałe konfiguracyjne dla widoków komparatora źródeł PBN."""

from datetime import datetime

CURRENT_YEAR = datetime.now().year
DEFAULT_ROK_OD = 2022
DEFAULT_ROK_DO = 2025
DEFAULT_SORT = "zrodlo__nazwa"
OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE = 20

VALID_SORT_FIELDS = [
    "zrodlo__nazwa",
    "-zrodlo__nazwa",
    "rok",
    "-rok",
    "punkty_bpp",
    "-punkty_bpp",
    "punkty_pbn",
    "-punkty_pbn",
    "updated_at",
    "-updated_at",
]

DYSCYPLINY_VALID_SORT_FIELDS = [
    "zrodlo__nazwa",
    "-zrodlo__nazwa",
    "rok",
    "-rok",
]
