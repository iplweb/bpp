import re

from braces.views import GroupRequiredMixin
from django.db.models import Q
from django.http import Http404
from django.utils.functional import cached_property
from django.views.generic import DetailView, ListView
from liveops.views import CreateLiveOperationView

from import_list_ministerialnych.forms import NowyImportForm
from import_list_ministerialnych.models import (
    ImportListMinisterialnych,
    WierszImportuListyMinisterialnej,
)

GROUP_REQUIRED = "wprowadzanie danych"


class PokazImporty(GroupRequiredMixin, ListView):
    """Lista importów bieżącego użytkownika.

    Dawniej long_running.LongRunningOperationsView. Teraz zwykły
    owner-scoped ListView — strona live (postęp/wynik) jest osobno, pod
    centralnym ``liveops:live`` (link przez ``object.get_absolute_url``).
    """

    group_required = GROUP_REQUIRED
    model = ImportListMinisterialnych

    def get_queryset(self):
        return self.model.objects.filter(owner=self.request.user).order_by(
            "-created_on"
        )


class UtworzImportDyscyplinZrodel(GroupRequiredMixin, CreateLiveOperationView):
    """Formularz nowego importu.

    ``CreateLiveOperationView`` (liveops) sam ustawia owner, zapisuje,
    kolejkuje operację i przekierowuje na ``get_absolute_url()`` czyli
    centralną stronę live. Gating grupy — braces GroupRequiredMixin
    (superuser-exempt, jak w long_running).
    """

    group_required = GROUP_REQUIRED
    model = ImportListMinisterialnych
    form_class = NowyImportForm


class ImportResultsBaseView(GroupRequiredMixin, ListView):
    """Baza dla filtrowanej tabeli wyników importu.

    Zastępuje dawną long_running.LongRunningResultsView: właściciel-scoping
    przez ``parent_object`` i queryset z ``get_details_set()``.
    """

    group_required = GROUP_REQUIRED
    paginate_by = 25
    model = ImportListMinisterialnych

    @cached_property
    def parent_object(self):
        o = self.model.objects.get(pk=self.kwargs["pk"])
        if o.owner != self.request.user:
            raise Http404
        return o

    def get_queryset(self):
        return self.parent_object.get_details_set()

    def get_context_data(self, **kwargs):
        return super().get_context_data(object=self.parent_object, **kwargs)


class ImportDyscyplinZrodelResultsView(ImportResultsBaseView):
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
        search_query = self.request.GET.get("search_query", "").strip()

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

        # Apply search query filter
        if search_query:
            # Extract row numbers from search query (comma-separated integers)
            row_numbers = re.findall(r"\d+", search_query)
            row_numbers = [int(num) for num in row_numbers] if row_numbers else []

            # Build Q filter with text search
            q_filter = (
                Q(zrodlo__nazwa__icontains=search_query)
                | Q(zrodlo__issn__icontains=search_query)
                | Q(zrodlo__e_issn__icontains=search_query)
                | Q(dane_z_xls__Tytul_1__icontains=search_query)
                | Q(dane_z_xls__issn__icontains=search_query)
                | Q(dane_z_xls__issn__1__icontains=search_query)
                | Q(dane_z_xls__e_issn__icontains=search_query)
                | Q(dane_z_xls__e_issn__1__icontains=search_query)
                | Q(rezultat__icontains=search_query)
            )

            # Add row number filter if numbers were found
            if row_numbers:
                q_filter |= Q(nr_wiersza__in=row_numbers)

            queryset = queryset.filter(q_filter)

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
        context["search_query"] = self.request.GET.get("search_query", "")

        return context


class WierszImportuListyMinisterialnejDetailView(GroupRequiredMixin, DetailView):
    group_required = GROUP_REQUIRED
    model = WierszImportuListyMinisterialnej
    pk_url_kwarg = "row_pk"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        # Get parent import object for breadcrumbs/back button
        context["parent"] = self.object.parent
        return context
