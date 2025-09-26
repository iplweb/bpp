from braces.views import GroupRequiredMixin

from import_list_ministerialnych.forms import NowyImportForm
from import_list_ministerialnych.models import ImportListMinisterialnych
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
    model = ImportListMinisterialnych


class PokazImporty(BaseImportDyscyplinZrodelMixin, LongRunningOperationsView):
    pass


class UtworzImportDyscyplinZrodel(
    BaseImportDyscyplinZrodelMixin, CreateLongRunningOperationView
):
    form_class = NowyImportForm


class ImportDyscyplinZrodelRouterView(
    BaseImportDyscyplinZrodelMixin, LongRunningRouterView
):
    redirect_prefix = "import_list_ministerialnych:ImportListMinisterialnych"


class ImportDyscyplinZrodelDetailsView(
    BaseImportDyscyplinZrodelMixin, LongRunningDetailsView
):
    pass


class RestartImportView(
    BaseImportDyscyplinZrodelMixin, RestartLongRunningOperationView
):
    pass


class ImportDyscyplinZrodelResultsView(
    BaseImportDyscyplinZrodelMixin, LongRunningResultsView
):
    def get_queryset(self):
        """Override to handle filtering parameters from URL"""
        queryset = super().get_queryset()

        # Get filter parameters from URL
        exclude_identical_punkty = (
            self.request.GET.get("exclude_identical_punkty") == "1"
        )
        exclude_identical_dyscypliny = (
            self.request.GET.get("exclude_identical_dyscypliny") == "1"
        )
        only_duplicates = self.request.GET.get("only_duplicates") == "1"

        # Apply filters
        if exclude_identical_punkty:
            queryset = queryset.exclude(
                rezultat__contains="Punktacja identyczna w BPP i w XLS"
            )

        if exclude_identical_dyscypliny:
            queryset = queryset.exclude(
                rezultat__contains="Dyscypliny zgodne w BPP i w XLSX"
            )

        if only_duplicates:
            queryset = queryset.filter(is_duplicate=True)

        return queryset

    def get_context_data(self, **kwargs):
        """Add statistics to context"""
        context = super().get_context_data(**kwargs)

        # Get the parent object from the URL
        parent_pk = self.kwargs["pk"]
        parent = self.model.objects.get(pk=parent_pk)

        # Calculate statistics for all records (not just filtered)
        all_records = parent.wierszimportulistyministerialnej_set.all()

        context["total_count"] = all_records.count()
        context["duplicate_count"] = all_records.filter(is_duplicate=True).count()
        context["identical_punkty_count"] = all_records.filter(
            rezultat__contains="Punktacja identyczna w BPP i w XLS"
        ).count()
        context["identical_dyscypliny_count"] = all_records.filter(
            rezultat__contains="Dyscypliny zgodne w BPP i w XLSX"
        ).count()

        # Pass current filter state to template
        context["exclude_identical_punkty"] = (
            self.request.GET.get("exclude_identical_punkty") == "1"
        )
        context["exclude_identical_dyscypliny"] = (
            self.request.GET.get("exclude_identical_dyscypliny") == "1"
        )
        context["only_duplicates"] = self.request.GET.get("only_duplicates") == "1"

        return context
