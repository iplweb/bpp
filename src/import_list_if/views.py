from braces.views import GroupRequiredMixin

from import_list_if.forms import NowyImportForm
from import_list_if.models import ImportListIf
from long_running.views import (
    CreateLongRunningOperationView,
    LongRunningDetailsView,
    LongRunningOperationsView,
    LongRunningResultsView,
    LongRunningRouterView,
    RestartLongRunningOperationView,
)


class BaseImportListIfMixin(GroupRequiredMixin):
    group_required = "wprowadzanie danych"
    model = ImportListIf


class ListaImportowView(BaseImportListIfMixin, LongRunningOperationsView):
    pass


class NowyImportView(BaseImportListIfMixin, CreateLongRunningOperationView):
    form_class = NowyImportForm


class ImportListIfRouterView(BaseImportListIfMixin, LongRunningRouterView):
    redirect_prefix = "import_list_if:import_list_if"


class ImportListIfDetailsView(BaseImportListIfMixin, LongRunningDetailsView):
    pass


class ImportListIfResultsView(BaseImportListIfMixin, LongRunningResultsView):
    pass


class RestartImportView(BaseImportListIfMixin, RestartLongRunningOperationView):
    pass
