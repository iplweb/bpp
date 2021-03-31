from braces.views import GroupRequiredMixin

from import_dyscyplin_zrodel.forms import NowyImportForm
from import_dyscyplin_zrodel.models import ImportDyscyplinZrodel
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
    model = ImportDyscyplinZrodel


class ListaImportowView(BaseImportDyscyplinZrodelMixin, LongRunningOperationsView):
    pass


class NowyImportView(BaseImportDyscyplinZrodelMixin, CreateLongRunningOperationView):
    form_class = NowyImportForm


class ImportDyscyplinZrodelRouterView(
    BaseImportDyscyplinZrodelMixin, LongRunningRouterView
):
    redirect_prefix = "import_dyscyplin_zrodel:ImportDyscyplinZrodel"


class ImportDyscyplinZrodelDetailsView(
    BaseImportDyscyplinZrodelMixin, LongRunningDetailsView
):
    pass


class ImportDyscyplinZrodelResultsView(
    BaseImportDyscyplinZrodelMixin, LongRunningResultsView
):
    pass


class RestartImportView(
    BaseImportDyscyplinZrodelMixin, RestartLongRunningOperationView
):
    pass
