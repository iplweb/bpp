# Create your views here.
from datetime import timedelta

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

from django.utils import timezone

from bpp.models import Autor_Jednostka, Uczelnia


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
        uczelnia = Uczelnia.objects.get_for_request(self.request)
        return (
            Autor_Jednostka.objects.exclude(
                autor_id__in=self.get_queryset().values_list("autor_id").distinct()
            )
            .exclude(autor__aktualna_jednostka_id=uczelnia.obca_jednostka_id)
            .exclude(jednostka__zarzadzaj_automatycznie=False)
            .select_related("autor", "autor__tytul", "jednostka", "jednostka__wydzial")
        )

    def get_context_data(self, **kwargs):
        return super().get_context_data(autorzy_spoza_pliku=self.autorzy_spoza_pliku())


class ImportPracownikowResetujPodstawoweMiejscePracyView(ImportPracownikowResultsView):
    def get(self, request, *args, **kwargs):
        today = timezone.now().date()
        yesterday = today - timedelta(days=1)

        uczelnia = Uczelnia.objects.get_for_request(self.request)

        seen_aut = set()

        self.autorzy_spoza_pliku().update(
            zakonczyl_prace=yesterday, podstawowe_miejsce_pracy=False
        )

        for autor_jednostka in self.autorzy_spoza_pliku():
            if autor_jednostka.autor_id in seen_aut:
                continue
            Autor_Jednostka.objects.get_or_create(
                autor_id=autor_jednostka.autor_id,
                jednostka=uczelnia.obca_jednostka,
                rozpoczal_prace=today,
            )
            seen_aut.add(autor_jednostka.autor_id)

        messages.info(
            request, "Podstawowe miejsca pracy autorów zostały zaktualizowane."
        )
        return HttpResponseRedirect("..")


class RestartImportView(BaseImportPracownikowMixin, RestartLongRunningOperationView):
    pass
