# Backwards compatibility layer - all views can be imported from ewaluacja_metryki.views
# This allows existing code to continue using:
#   from ewaluacja_metryki.views import MetrykiListView
# instead of:
#   from ewaluacja_metryki.views.list import MetrykiListView

# Re-export task for backwards compatibility (used by tests that patch at module level)
from ..tasks import generuj_metryki_task_parallel
from .detail import MetrykaDetailView
from .export import ExportListaXLSX, ExportStatystykiXLSX
from .generation import (
    StatusGenerowaniaPartialView,
    StatusGenerowaniaView,
    UruchomGenerowanieView,
)
from .list import MetrykiListView
from .mixins import EwaluacjaRequiredMixin, ma_uprawnienia_ewaluacji
from .pin_unpin import OdepnijDyscyplineView, PrzypnijDyscyplineView
from .statistics import StatystykiView

__all__ = [
    # Mixins and utilities
    "ma_uprawnienia_ewaluacji",
    "EwaluacjaRequiredMixin",
    # List view
    "MetrykiListView",
    # Detail view
    "MetrykaDetailView",
    # Pin/Unpin views
    "PrzypnijDyscyplineView",
    "OdepnijDyscyplineView",
    # Statistics view
    "StatystykiView",
    # Generation views
    "UruchomGenerowanieView",
    "StatusGenerowaniaView",
    "StatusGenerowaniaPartialView",
    # Export views
    "ExportStatystykiXLSX",
    "ExportListaXLSX",
    # Tasks (for backwards compatibility)
    "generuj_metryki_task_parallel",
]
