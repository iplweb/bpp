from braces.views import GroupRequiredMixin

from import_polon.forms import NowyImportForm
from import_polon.models import ImportPlikuPolon
from long_running.views import (
    CreateLongRunningOperationView,
    LongRunningDetailsView,
    LongRunningOperationsView,
    LongRunningResultsView,
    LongRunningRouterView,
    RestartLongRunningOperationView,
)


class BaseImportPlikuPolonMixin(GroupRequiredMixin):
    group_required = "wprowadzanie danych"
    model = ImportPlikuPolon


class PokazImporty(BaseImportPlikuPolonMixin, LongRunningOperationsView):
    pass


class UtworzImportPlikuPolon(BaseImportPlikuPolonMixin, CreateLongRunningOperationView):
    form_class = NowyImportForm


class ImportPolonRouterView(BaseImportPlikuPolonMixin, LongRunningRouterView):
    redirect_prefix = "import_polon:importplikupolon"


class ImportPolonDetailsView(BaseImportPlikuPolonMixin, LongRunningDetailsView):
    pass


class RestartImportView(BaseImportPlikuPolonMixin, RestartLongRunningOperationView):
    pass


class ImportPolonResultsView(BaseImportPlikuPolonMixin, LongRunningResultsView):
    pass
