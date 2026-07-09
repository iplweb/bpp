# Create your views here.

from braces.views import GroupRequiredMixin
from django.contrib import messages
from django.http import Http404, HttpResponseRedirect
from django.shortcuts import get_object_or_404
from django.views.generic import ListView
from liveops.views import CreateLiveOperationView, RestartView

from bpp.models import Uczelnia
from import_pracownikow.forms import NowyImportForm
from import_pracownikow.models import ImportPracownikow

GROUP_REQUIRED = "wprowadzanie danych"


class ListaImportowView(GroupRequiredMixin, ListView):
    """Lista importów bieżącego użytkownika.

    Dawniej long_running.LongRunningOperationsView. Teraz zwykły owner-scoped
    ListView — strona live (postęp/wynik) jest osobno, pod centralnym
    ``liveops:live`` (link przez ``object.get_absolute_url``).
    """

    group_required = GROUP_REQUIRED
    model = ImportPracownikow
    template_name = "import_pracownikow/importpracownikow_list.html"

    def get_queryset(self):
        return ImportPracownikow.objects.filter(owner=self.request.user).order_by(
            "-created_on"
        )


class NowyImportView(GroupRequiredMixin, CreateLiveOperationView):
    """Formularz nowego importu.

    ``CreateLiveOperationView`` (liveops) sam ustawia owner, zapisuje,
    kolejkuje operację i przekierowuje na ``get_absolute_url()`` czyli
    centralną stronę live. Gating grupy — braces GroupRequiredMixin
    (superuser-exempt, jak w long_running).
    """

    group_required = GROUP_REQUIRED
    model = ImportPracownikow
    form_class = NowyImportForm


class ImportPracownikowResultsView(GroupRequiredMixin, ListView):
    """Filtrowalna tabela wyników importu (dopasowani/niedopasowani autorzy).

    Zastępuje dawną long_running.LongRunningResultsView: właściciel-scoping
    przez ``parent_object`` i queryset z ``get_details_set()``. Strona live
    (liveops:live) linkuje tu przez panel wyniku po zakończeniu importu.
    """

    group_required = GROUP_REQUIRED
    template_name = "import_pracownikow/importpracownikowrow_list.html"
    context_object_name = "object_list"

    @property
    def parent_object(self):
        obj = get_object_or_404(ImportPracownikow, pk=self.kwargs["pk"])
        if obj.owner_id != self.request.user.pk and not self.request.user.is_superuser:
            raise Http404
        return obj

    def get_queryset(self):
        return self.parent_object.get_details_set()

    def autorzy_spoza_pliku(self):
        uczelnia = Uczelnia.objects.get_for_request(self.request)
        return self.parent_object.autorzy_spoza_pliku_set(
            uczelnia=uczelnia
        ).select_related("autor", "autor__tytul", "jednostka", "jednostka__wydzial")

    def get_context_data(self, **kwargs):
        return super().get_context_data(
            parent_object=self.parent_object,
            autorzy_spoza_pliku=self.autorzy_spoza_pliku(),
            **kwargs,
        )


class ImportPracownikowResetujPodstawoweMiejscePracyView(ImportPracownikowResultsView):
    def get(self, request, *args, **kwargs):
        uczelnia = Uczelnia.objects.get_for_request(self.request)
        self.parent_object.odepnij_autorow_spoza_pliku(uczelnia=uczelnia)
        messages.info(
            request, "Podstawowe miejsca pracy autorów zostały zaktualizowane."
        )
        return HttpResponseRedirect("..")


class _PkOwnerRestartMixin(RestartView):
    """Wspólny ``get_object`` dla widoków restartu — URL ma tylko ``pk``
    (bez ``op_type``), więc nadpisujemy ``OpTypeObjectMixin.get_object``
    i rozwiązujemy konkretny model wprost, owner-scoped."""

    model = ImportPracownikow

    def get_object(self, queryset=None):
        return get_object_or_404(
            ImportPracownikow, pk=self.kwargs["pk"], owner=self.request.user
        )


class ZatwierdzImportView(_PkOwnerRestartMixin):
    """Zatwierdza dry-run (analizę) i uruchamia integrację na już
    zapisanym pliku (bez ponownego uploadu).

    Ustawiamy stan na ``zatwierdzony`` (żeby ``on_restart()`` NIE skasował
    wierszy podglądu — kasuje tylko gdy stan==utworzony) i delegujemy
    resztę do bazowego POST-a liveops ``RestartView`` (reset stanu
    operacji, re-enqueue, przekierowanie na stronę live).
    """

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.stan = ImportPracownikow.STAN_ZATWIERDZONY
        obj.save(update_fields=["stan"])
        return super().post(request, *args, **kwargs)


class RestartAnalizaView(_PkOwnerRestartMixin):
    """Cofa import do stanu ``utworzony`` i uruchamia analizę od nowa.

    Ustawiamy stan na ``utworzony`` PRZED wywołaniem bazowego POST-a, żeby
    ``on_restart()`` skasował istniejące wiersze podglądu (dry-run od zera).
    """

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.stan = ImportPracownikow.STAN_UTWORZONY
        obj.save(update_fields=["stan"])
        return super().post(request, *args, **kwargs)
