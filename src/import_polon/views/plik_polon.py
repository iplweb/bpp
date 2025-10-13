from braces.views import GroupRequiredMixin
from django.db.models import Count, Q

from import_polon.forms import NowyImportForm, WierszImportuPlikuPolonFilterForm
from import_polon.models import ImportPlikuPolon
from long_running.views import (
    CreateLongRunningOperationView,
    LongRunningDetailsView,
    LongRunningOperationsView,
    LongRunningResultsView,
    LongRunningRouterView,
    RestartLongRunningOperationView,
)

from bpp.models import Autor_Dyscyplina


class BaseImportPlikuPolonMixin(GroupRequiredMixin):
    group_required = "wprowadzanie danych"
    model = ImportPlikuPolon


class PokazImporty(BaseImportPlikuPolonMixin, LongRunningOperationsView):
    pass


class UtworzImportPlikuPolon(BaseImportPlikuPolonMixin, CreateLongRunningOperationView):
    form_class = NowyImportForm


class ImportPolonRouterView(BaseImportPlikuPolonMixin, LongRunningRouterView):
    redirect_prefix = "import_polon:importplikuabsencji"


class ImportPolonDetailsView(BaseImportPlikuPolonMixin, LongRunningDetailsView):
    pass


class RestartImportView(BaseImportPlikuPolonMixin, RestartLongRunningOperationView):
    pass


class ImportPolonResultsView(BaseImportPlikuPolonMixin, LongRunningResultsView):
    def get_queryset(self):
        queryset = super().get_queryset()

        # Get filter parameters
        autor_wiersz = self.request.GET.get("autor_wiersz", "").strip()
        dyscyplina = self.request.GET.get("dyscyplina", "").strip()
        grupa_stanowisk = self.request.GET.get("grupa_stanowisk", "").strip()

        # Apply combined autor/wiersz filter
        if autor_wiersz:
            try:
                # Try to convert to int for row number filtering
                wiersz_int = int(autor_wiersz)
                queryset = queryset.filter(nr_wiersza=wiersz_int)
            except ValueError:
                # If not a number, search in author fields and result
                queryset = queryset.filter(
                    Q(dane_z_xls__NAZWISKO__icontains=autor_wiersz)
                    | Q(dane_z_xls__IMIE__icontains=autor_wiersz)
                    | Q(rezultat__icontains=autor_wiersz)
                )

        # Apply combined dyscyplina filter (searches both dyscyplina and subdyscyplina)
        if dyscyplina:
            queryset = queryset.filter(
                Q(dane_z_xls__DYSCYPLINA_N__icontains=dyscyplina)
                | Q(dane_z_xls__DYSCYPLINA_N_KOLEJNA__icontains=dyscyplina)
            )

        # Apply grupa stanowisk filter
        if grupa_stanowisk:
            queryset = queryset.filter(
                dane_z_xls__GRUPA_STANOWISK__icontains=grupa_stanowisk
            )

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Get base queryset for form choices
        base_queryset = ImportPlikuPolon.objects.get(
            pk=self.kwargs["pk"]
        ).get_details_set()

        # Create filter form with current GET parameters and queryset for choices
        filter_form = WierszImportuPlikuPolonFilterForm(
            data=self.request.GET or None, queryset=base_queryset
        )

        context["filter_form"] = filter_form

        # Add flag to indicate if filtering is active
        context["is_filtered"] = bool(
            self.request.GET.get("autor_wiersz")
            or self.request.GET.get("dyscyplina")
            or self.request.GET.get("grupa_stanowisk")
        )

        # Get unmatched Autor_Dyscyplina records for this import year
        import_object = ImportPlikuPolon.objects.get(pk=self.kwargs["pk"])

        # Get all authors that were matched in the import
        matched_authors = base_queryset.filter(autor__isnull=False).values_list(
            "autor_id", flat=True
        )

        # Get all Autor_Dyscyplina records for the import year that are NOT in the matched authors
        unmatched_autor_dyscyplina = (
            Autor_Dyscyplina.objects.filter(rok=import_object.rok)
            .exclude(autor_id__in=matched_authors)
            .select_related(
                "autor", "dyscyplina_naukowa", "subdyscyplina_naukowa", "rodzaj_autora"
            )
            .annotate(
                liczba_prac=Count(
                    "autor__autorzy",
                    filter=Q(autor__autorzy__rekord__rok=import_object.rok),
                )
            )
            .order_by("autor__nazwisko", "autor__imiona")
        )

        context["unmatched_autor_dyscyplina"] = unmatched_autor_dyscyplina
        context["unmatched_count"] = unmatched_autor_dyscyplina.count()

        return context
