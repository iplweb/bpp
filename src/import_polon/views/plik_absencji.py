from import_polon.forms import NowyImportAbsencjiForm
from import_polon.models import ImportPlikuAbsencji
from import_polon.views.plik_polon import BaseImportPlikuPolonMixin
from long_running.views import (
    CreateLongRunningOperationView,
    LongRunningDetailsView,
    LongRunningOperationsView,
    LongRunningResultsView,
    LongRunningRouterView,
    RestartLongRunningOperationView,
)


class BaseImportPlikuAbsencjiMixin(BaseImportPlikuPolonMixin):
    model = ImportPlikuAbsencji


class PokazImportPlikuAbsencji(BaseImportPlikuAbsencjiMixin, LongRunningOperationsView):
    pass


class UtworzImportPlikuAbsencji(
    BaseImportPlikuAbsencjiMixin, CreateLongRunningOperationView
):
    form_class = NowyImportAbsencjiForm


class ImportAbsencjiRouterView(BaseImportPlikuAbsencjiMixin, LongRunningRouterView):
    redirect_prefix = "import_polon:importplikabsencji"


class ImportAbsencjiDetailsView(BaseImportPlikuAbsencjiMixin, LongRunningDetailsView):
    pass


class RestartImportAbsencjiView(
    BaseImportPlikuAbsencjiMixin, RestartLongRunningOperationView
):
    pass


class ImportAbsencjiResultsView(BaseImportPlikuAbsencjiMixin, LongRunningResultsView):
    pass
