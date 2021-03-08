from braces.views import GroupRequiredMixin

from import_list_if.forms import NowyImportForm
from import_list_if.models import ImportListIf
from long_running.views import (
    CreateLongRunningOperationView,
    LongRunningDetailsView,
    LongRunningOperationsView,
    RestartLongRunningOperationView,
)


class BaseImportListIfMixin(GroupRequiredMixin):
    group_required = "wprowadzanie danych"
    model = ImportListIf


class ListaImportowView(BaseImportListIfMixin, LongRunningOperationsView):
    pass


class NowyImportView(BaseImportListIfMixin, CreateLongRunningOperationView):
    form_class = NowyImportForm


class DetaleImportView(BaseImportListIfMixin, LongRunningDetailsView):
    pass


class RestartImportView(BaseImportListIfMixin, RestartLongRunningOperationView):
    pass
