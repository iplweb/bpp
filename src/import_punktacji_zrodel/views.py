from braces.views import GroupRequiredMixin
from django.db import transaction
from django.http import HttpResponseRedirect
from django.views.generic import DetailView

from import_punktacji_zrodel.forms import NowyImportForm
from import_punktacji_zrodel.models import ImportPunktacjiZrodel
from long_running.views import (
    CreateLongRunningOperationView,
    LongRunningDetailsView,
    LongRunningOperationsView,
    LongRunningResultsView,
    LongRunningRouterView,
    LongRunningTaskCallerMixin,
    RestartLongRunningOperationView,
    RestrictToOwnerMixin,
)


class BaseMixin(GroupRequiredMixin):
    group_required = "wprowadzanie danych"
    model = ImportPunktacjiZrodel


class ListaImportowView(BaseMixin, LongRunningOperationsView):
    pass


class NowyImportView(BaseMixin, CreateLongRunningOperationView):
    form_class = NowyImportForm


class RouterView(BaseMixin, LongRunningRouterView):
    pass


class DetailsView(BaseMixin, LongRunningDetailsView):
    pass


class ResultsView(BaseMixin, LongRunningResultsView):
    def get_queryset(self):
        qs = super().get_queryset()
        if self.request.GET.get("tylko_do_aktualizacji") == "1":
            qs = qs.filter(wymaga_zmian=True)
        if self.request.GET.get("tylko_niedopasowane") == "1":
            qs = qs.filter(zrodlo__isnull=True)
        if self.request.GET.get("tylko_duplikaty") == "1":
            qs = qs.filter(is_duplicate=True)
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        wszystkie = self.parent_object.get_details_set()
        ctx["total_count"] = wszystkie.count()
        ctx["do_aktualizacji_count"] = wszystkie.filter(wymaga_zmian=True).count()
        ctx["niedopasowane_count"] = wszystkie.filter(zrodlo__isnull=True).count()
        ctx["duplikaty_count"] = wszystkie.filter(is_duplicate=True).count()
        ctx["rok"] = self.parent_object.rok
        ctx["byl_dry_run"] = not self.parent_object.zapisz_zmiany_do_bazy
        return ctx


class RestartImportView(BaseMixin, RestartLongRunningOperationView):
    pass


class ZatwierdzImportView(
    BaseMixin, RestrictToOwnerMixin, LongRunningTaskCallerMixin, DetailView
):
    """Przełącza dry-run -> commit i ponownie uruchamia przetwarzanie
    na już zapisanym pliku (bez ponownego uploadu)."""

    http_method_names = ["post"]

    @transaction.atomic
    def post(self, *args, **kwargs):
        self.object = self.get_object()
        self.object.zapisz_zmiany_do_bazy = True
        self.object.save(update_fields=["zapisz_zmiany_do_bazy"])
        self.object.mark_reset()
        self.task_on_commit(pk=self.object.pk)
        return HttpResponseRedirect(self.object.get_url("router"))
