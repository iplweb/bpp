from braces.views import GroupRequiredMixin

from import_list_ministerialnych.forms import NowyImportForm
from import_list_ministerialnych.models import ImportListMinisterialnych
from long_running.views import (
    CreateLongRunningOperationView,
    LongRunningDetailsView,
    LongRunningOperationsView,
    LongRunningResultsView,
    LongRunningRouterView,
    RestartLongRunningOperationView,
)


class BaseImportDyscyplinZrodelMixin(GroupRequiredMixin):
    group_required = "wprowadzanie danych"
    model = ImportListMinisterialnych


class PokazImporty(BaseImportDyscyplinZrodelMixin, LongRunningOperationsView):
    pass


class UtworzImportDyscyplinZrodel(
    BaseImportDyscyplinZrodelMixin, CreateLongRunningOperationView
):
    form_class = NowyImportForm


class ImportDyscyplinZrodelRouterView(
    BaseImportDyscyplinZrodelMixin, LongRunningRouterView
):
    redirect_prefix = "import_list_ministerialnych:ImportListMinisterialnych"


class ImportDyscyplinZrodelDetailsView(
    BaseImportDyscyplinZrodelMixin, LongRunningDetailsView
):
    pass


class RestartImportView(
    BaseImportDyscyplinZrodelMixin, RestartLongRunningOperationView
):
    pass


class ImportDyscyplinZrodelResultsView(
    BaseImportDyscyplinZrodelMixin, LongRunningResultsView
):
    pass
