# Create your views here.
from braces.views import GroupRequiredMixin
from django.http import HttpResponseRedirect

from import_pracownikow.forms import NowyImportForm
from import_pracownikow.models import ImportPracownikow
from long_running.views import (
    CreateLongRunningOperationView,
    LongRunningDetailsView,
    LongRunningOperationsView,
    LongRunningResultsView,
    LongRunningRouterView,
    RestartLongRunningOperationView,
)

from django.contrib import messages

from bpp.models import Autor_Jednostka


class BaseImportPracownikowMixin(GroupRequiredMixin):
    group_required = "wprowadzanie danych"
    model = ImportPracownikow


class ListaImportowView(BaseImportPracownikowMixin, LongRunningOperationsView):
    pass


class NowyImportView(BaseImportPracownikowMixin, CreateLongRunningOperationView):
    form_class = NowyImportForm


class ImportPracownikowRouterView(BaseImportPracownikowMixin, LongRunningRouterView):
    redirect_prefix = "import_pracownikow:import_pracownikow"


class ImportPracownikowDetailsView(BaseImportPracownikowMixin, LongRunningDetailsView):
    pass


class ImportPracownikowResultsView(BaseImportPracownikowMixin, LongRunningResultsView):
    def autorzy_spoza_pliku(self):
        return (
            Autor_Jednostka.objects.exclude(
                pk__in=self.get_queryset().values_list("autor_jednostka_id").distinct()
            )
            .filter(podstawowe_miejsce_pracy=True)
            .select_related("autor", "autor__tytul", "jednostka", "jednostka__wydzial")
        )

    def get_context_data(self, **kwargs):
        return super().get_context_data(autorzy_spoza_pliku=self.autorzy_spoza_pliku())


class ImportPracownikowResetujPodstawoweMiejscePracyView(ImportPracownikowResultsView):
    def get(self, request, *args, **kwargs):
        self.autorzy_spoza_pliku().update(podstawowe_miejsce_pracy=False)
        messages.info(
            request, "Podstawowe miejsca pracy autorów zostały zaktualizowane."
        )
        return HttpResponseRedirect("..")


class RestartImportView(BaseImportPracownikowMixin, RestartLongRunningOperationView):
    pass
