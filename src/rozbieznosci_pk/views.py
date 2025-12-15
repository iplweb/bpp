"""Views for punkty_kbn discrepancies - reuses base classes from rozbieznosci_if."""

from rozbieznosci_if.views import (
    BaseRozbieznosciExportView,
    BaseRozbieznosciView,
    BaseTaskStatusView,
    BaseUstawWszystkieView,
)
from rozbieznosci_pk.models import IgnorujRozbieznoscPk, RozbieznosciPkLog


class RozbieznosciPkView(BaseRozbieznosciView):
    """Punkty MNiSW discrepancies view."""

    template_name = "rozbieznosci_pk/index.html"
    field_name = "punkty_kbn"
    field_label = "punkty MNiSW"
    ignore_model = IgnorujRozbieznoscPk
    log_model = RozbieznosciPkLog
    log_before_field = "pk_before"
    log_after_field = "pk_after"
    app_name = "rozbieznosci_pk"
    page_title = "Rozbieżności punktacji MNiSW"
    panel_class = "pk-panel"


class RozbieznosciPkExportView(BaseRozbieznosciExportView):
    """Export punkty MNiSW discrepancies to XLSX."""

    field_name = "punkty_kbn"
    field_label = "punkty MNiSW"
    ignore_model = IgnorujRozbieznoscPk
    sheet_title = "Rozbieżności punktów MNiSW"
    filename_prefix = "rozbieznosci_pk"
    table_title = "RozbieznosciPK"


class UstawWszystkiePkView(BaseUstawWszystkieView):
    """Set punkty_kbn from source for all filtered records."""

    field_name = "punkty_kbn"
    field_label = "punkty MNiSW"
    ignore_model = IgnorujRozbieznoscPk
    log_model = RozbieznosciPkLog
    log_before_field = "pk_before"
    log_after_field = "pk_after"
    app_name = "rozbieznosci_pk"

    def get_celery_task(self):
        from rozbieznosci_pk.tasks import task_ustaw_pk_ze_zrodla

        return task_ustaw_pk_ze_zrodla


class TaskStatusPkView(BaseTaskStatusView):
    """Display punkty MNiSW task progress with HTMX polling."""

    app_name = "rozbieznosci_pk"
    template_name = "rozbieznosci_pk/task_status.html"
    progress_template_name = "rozbieznosci_pk/_progress.html"
    page_title = "Rozbieżności punktacji MNiSW"
