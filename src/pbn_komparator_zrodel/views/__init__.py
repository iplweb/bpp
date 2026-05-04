"""Pakiet widoków komparatora źródeł PBN.

Pierwotny moduł `views.py` został rozbity na mniejsze pliki tematyczne.
Ten `__init__.py` re-eksportuje pełne publiczne API, dzięki czemu
istniejące importy (np. z `urls.py`) działają bez zmian.

Struktura:
- ``constants``       — stałe (lata, sortowanie, progi),
- ``forms``           — `FilterForm`, `DyscyplinyFilterForm`,
- ``list_views``      — widoki list rozbieżności (punktów i dyscyplin),
- ``export_views``    — eksport rozbieżności do XLSX,
- ``update_views``    — aktualizacja pojedyncza i masowa,
- ``task_views``      — przebudowa rozbieżności i status zadań Celery.
"""

from .constants import (
    CURRENT_YEAR,
    DEFAULT_ROK_DO,
    DEFAULT_ROK_OD,
    DEFAULT_SORT,
    DYSCYPLINY_VALID_SORT_FIELDS,
    OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE,
    VALID_SORT_FIELDS,
)
from .export_views import ExportDyscyplinyXlsxView, ExportXlsxView
from .forms import DyscyplinyFilterForm, FilterForm
from .list_views import RozbieznosciDyscyplinListView, RozbieznosciZrodelListView
from .task_views import PrzebudujRozbieznosciView, TaskStatusView
from .update_views import (
    AktualizujPojedynczyView,
    AktualizujWszystkieDyscyplinyView,
    AktualizujWszystkieView,
)

__all__ = [
    # Stałe
    "CURRENT_YEAR",
    "DEFAULT_ROK_OD",
    "DEFAULT_ROK_DO",
    "DEFAULT_SORT",
    "DYSCYPLINY_VALID_SORT_FIELDS",
    "OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE",
    "VALID_SORT_FIELDS",
    # Formularze
    "FilterForm",
    "DyscyplinyFilterForm",
    # Widoki list
    "RozbieznosciZrodelListView",
    "RozbieznosciDyscyplinListView",
    # Eksport
    "ExportDyscyplinyXlsxView",
    "ExportXlsxView",
    # Aktualizacja
    "AktualizujPojedynczyView",
    "AktualizujWszystkieView",
    "AktualizujWszystkieDyscyplinyView",
    # Zadania
    "PrzebudujRozbieznosciView",
    "TaskStatusView",
]
