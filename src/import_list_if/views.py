from braces.views import GroupRequiredMixin
from django.http import Http404
from django.shortcuts import get_object_or_404
from django.utils.functional import cached_property
from django.views.generic import ListView
from liveops.views import CreateLiveOperationView

from bpp.const import GR_WPROWADZANIE_DANYCH
from import_list_if.forms import NowyImportForm
from import_list_if.models import ImportListIf


class BaseImportListIfMixin(GroupRequiredMixin):
    # Bramka grupy przez braces (superuser-exempt). liveops gejtuje grupą tylko
    # przy LIVEOPS["REQUIRED_GROUP"], którego BPP nie ustawia — stąd braces.
    group_required = GR_WPROWADZANIE_DANYCH
    model = ImportListIf


class ListaImportowView(BaseImportListIfMixin, ListView):
    """Lista importów bieżącego użytkownika (owner-scoped).

    Dawniej long_running.LongRunningOperationsView. Strona live (postęp/wynik)
    jest osobno, pod centralnym ``liveops:live`` (link przez get_absolute_url).
    """

    def get_queryset(self):
        return self.model.objects.filter(owner=self.request.user).order_by(
            "-created_on"
        )


class NowyImportView(BaseImportListIfMixin, CreateLiveOperationView):
    """Formularz nowego importu.

    ``CreateLiveOperationView`` (liveops) ustawia owner, zapisuje, kolejkuje
    operację i przekierowuje na ``get_absolute_url()`` (centralna strona live).
    """

    form_class = NowyImportForm


class ImportListIfResultsView(BaseImportListIfMixin, ListView):
    """Tabela wyników importu (owner-scoped).

    Zastępuje long_running.LongRunningResultsView. Queryset to wiersze z
    ``get_details_set()`` (model ImportListIfRow → szablon
    import_list_if/importlistifrow_list.html), a ``object`` w kontekście to
    rodzic (ImportListIf) — szablon używa object.plik_xls.name i paginacji.
    """

    paginate_by = 25

    @cached_property
    def parent_object(self):
        # Nieistniejący pk → 404 (nie 500); parytet z get_object_or_404 we
        # wzorcu import_pracownikow. Owner-mismatch też 404 (nie ujawniamy
        # istnienia cudzej operacji).
        o = get_object_or_404(self.model, pk=self.kwargs["pk"])
        if o.owner != self.request.user:
            raise Http404
        return o

    def get_queryset(self):
        return self.parent_object.get_details_set()

    def get_context_data(self, **kwargs):
        return super().get_context_data(object=self.parent_object, **kwargs)
