# Create your views here.
from braces.views import GroupRequiredMixin

from import_pracownikow.forms import NowyImportForm
from import_pracownikow.models import ImportPracownikow
from long_running.views import (
    CreateLongRunningOperationView,
    LongRunningDetailsView,
    LongRunningOperationsView,
    RestartLongRunningOperationView,
)


class BaseImportPracownikowMixin(GroupRequiredMixin):
    group_required = "wprowadzanie danych"
    model = ImportPracownikow


class ListaImportowView(BaseImportPracownikowMixin, LongRunningOperationsView):
    pass


class NowyImportView(BaseImportPracownikowMixin, CreateLongRunningOperationView):
    form_class = NowyImportForm


class DetaleImportView(BaseImportPracownikowMixin, LongRunningDetailsView):
    pass


class RestartImportView(BaseImportPracownikowMixin, RestartLongRunningOperationView):
    pass
