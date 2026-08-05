from braces.views import GroupRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property
from django.views.generic import ListView
from liveops.views import CreateLiveOperationView, RestartView

from import_punktacji_zrodel.forms import NowyImportForm
from import_punktacji_zrodel.models import ImportPunktacjiZrodel

GROUP_REQUIRED = "wprowadzanie danych"


class ListaImportowView(GroupRequiredMixin, ListView):
    """Lista importów bieżącego użytkownika.

    Dawniej long_running.LongRunningOperationsView. Teraz zwykły owner-scoped
    ListView — strona live (postęp/wynik) jest osobno, pod centralnym
    ``liveops:live`` (link przez ``object.get_absolute_url``).
    """

    group_required = GROUP_REQUIRED
    model = ImportPunktacjiZrodel

    def get_queryset(self):
        return self.model.objects.filter(owner=self.request.user).order_by(
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
    model = ImportPunktacjiZrodel
    form_class = NowyImportForm


class ResultsView(GroupRequiredMixin, ListView):
    """Filtrowalna tabela wyników importu.

    Zastępuje dawną long_running.LongRunningResultsView: właściciel-scoping
    przez ``parent_object`` i queryset z ``get_details_set()``. Strona live
    (liveops:live) linkuje tu przez panel wyniku po zakończeniu importu.
    """

    group_required = GROUP_REQUIRED
    paginate_by = 25
    model = ImportPunktacjiZrodel

    @cached_property
    def parent_object(self):
        o = self.model.objects.get(pk=self.kwargs["pk"])
        if o.owner != self.request.user:
            raise Http404
        return o

    def get_queryset(self):
        qs = self.parent_object.get_details_set()
        if self.request.GET.get("tylko_do_aktualizacji") == "1":
            qs = qs.filter(wymaga_zmian=True)
        if self.request.GET.get("tylko_niedopasowane") == "1":
            qs = qs.filter(zrodlo__isnull=True)
        if self.request.GET.get("tylko_duplikaty") == "1":
            qs = qs.filter(is_duplicate=True)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(object=self.parent_object, **kwargs)
        wszystkie = self.parent_object.get_details_set()
        ctx["total_count"] = wszystkie.count()
        ctx["do_aktualizacji_count"] = wszystkie.filter(wymaga_zmian=True).count()
        ctx["niedopasowane_count"] = wszystkie.filter(zrodlo__isnull=True).count()
        ctx["duplikaty_count"] = wszystkie.filter(is_duplicate=True).count()
        ctx["rok"] = self.parent_object.rok
        ctx["byl_dry_run"] = not self.parent_object.zapisz_zmiany_do_bazy
        return ctx


class ZatwierdzImportView(RestartView):
    """Przełącza dry-run -> commit i ponownie uruchamia przetwarzanie na już
    zapisanym pliku (bez ponownego uploadu).

    Commit dry-runu to dokładnie „reset stanu + on_restart() + re-enqueue" —
    czyli to co robi liveops ``RestartView``. Ustawiamy tylko flagę
    ``zapisz_zmiany_do_bazy`` i delegujemy resztę do bazowego POST-a (który
    woła on_restart() kasujący wiersze podglądu, resetuje stan operacji,
    kolejkuje ponownie i przekierowuje na stronę live). Owner-scoping i
    bramka grupy — przez BaseLiveOperationMixin z RestartView.
    """

    model = ImportPunktacjiZrodel

    def get_object(self, queryset=None):
        # Nadpisujemy OpTypeObjectMixin.get_object (URL ma tu tylko pk, bez
        # op_type) — rozwiązujemy konkretny model wprost, owner-scoped.
        return get_object_or_404(
            ImportPunktacjiZrodel, pk=self.kwargs["pk"], owner=self.request.user
        )

    def post(self, request, *args, **kwargs):
        obj = self.get_object()
        obj.zapisz_zmiany_do_bazy = True
        obj.save(update_fields=["zapisz_zmiany_do_bazy"])
        return super().post(request, *args, **kwargs)
