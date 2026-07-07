from braces.views import GroupRequiredMixin
from django.db import transaction
from django.db.models import Q
from django.http import HttpResponseRedirect
from django.views.generic import DetailView

from import_polon.forms import NowyImportForm, WierszImportuPlikuPolonFilterForm
from import_polon.models import ImportPlikuPolon
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


class ZapiszDoBazyMixin(RestrictToOwnerMixin, LongRunningTaskCallerMixin, DetailView):
    """Domknięcie dry-runa zapisem do bazy.

    Gdy import uruchomiono bez zapisu (``zapisz_zmiany_do_bazy=False``), ta akcja
    przestawia flagę na ``True`` i resetuje obiekt do ponownego uruchomienia —
    „taki reset, ALE tym razem modyfikuj bazę". GET pokazuje stronę
    potwierdzenia; dopiero POST modyfikuje bazę (prefetch/robot nie wywoła
    zapisu). ``mark_reset`` czyści stan i kasuje wiersze-dzieci; ponowne
    ``perform()`` — tym razem z zapisem — kolejkuje ``task_on_commit``.
    """

    template_name = "import_polon/potwierdz_zapis_do_bazy.html"

    @transaction.atomic
    def post(self, *args, **kwargs):
        self.object = self.get_object()
        # Guard: tylko zakończony dry-run można domknąć zapisem. Import już
        # zapisany do bazy pomijamy — ochrona przed podwójnym zapisem.
        if (
            self.object.finished_on is not None
            and not self.object.zapisz_zmiany_do_bazy
        ):
            self.object.zapisz_zmiany_do_bazy = True
            self.object.mark_reset()
            self.task_on_commit(pk=self.object.pk)
        return HttpResponseRedirect("..")


class BaseImportPlikuPolonMixin(GroupRequiredMixin):
    group_required = "wprowadzanie danych"
    model = ImportPlikuPolon


class PokazImporty(BaseImportPlikuPolonMixin, LongRunningOperationsView):
    pass


class UtworzImportPlikuPolon(BaseImportPlikuPolonMixin, CreateLongRunningOperationView):
    form_class = NowyImportForm

    def form_valid(self, form):
        # Multi-hosted: przypnij import do uczelni z requestu (domena→Site→
        # Uczelnia). Zawęża późniejszą walidację ZATRUDNIENIE, dopasowanie
        # autora i raport niezmatchowanych do tej jednej uczelni. Gdy nie da
        # się rozstrzygnąć (single-host bez domeny / pusta baza) → None →
        # zachowanie wsteczne bez zawężenia.
        from bpp.models import Uczelnia

        form.instance.uczelnia = Uczelnia.objects.get_for_request(self.request)
        return super().form_valid(form)


class ImportPolonRouterView(BaseImportPlikuPolonMixin, LongRunningRouterView):
    redirect_prefix = "import_polon:importplikuabsencji"


class ImportPolonDetailsView(BaseImportPlikuPolonMixin, LongRunningDetailsView):
    pass


class RestartImportView(BaseImportPlikuPolonMixin, RestartLongRunningOperationView):
    pass


class ZapiszDoBazyImportView(BaseImportPlikuPolonMixin, ZapiszDoBazyMixin):
    pass


class ImportPolonResultsView(BaseImportPlikuPolonMixin, LongRunningResultsView):
    def get_queryset(self):
        queryset = super().get_queryset()

        # Get filter parameters
        autor_wiersz = self.request.GET.get("autor_wiersz", "").strip()
        dyscyplina = self.request.GET.get("dyscyplina", "").strip()
        grupa_stanowisk = self.request.GET.get("grupa_stanowisk", "").strip()
        pokaz_tylko_roznice = self.request.GET.get("pokaz_tylko_roznice", "")

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

        # Apply "show only differences" filter
        if pokaz_tylko_roznice:
            queryset = queryset.exclude(
                rezultat__startswith="W BPP jest identycznie jak w XLSX"
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
            or self.request.GET.get("pokaz_tylko_roznice")
        )

        # Autorzy z dyscyplinami dla roku importu, których nie było w pliku.
        # Multi-hosted: zawężone do aktualnie zatrudnionych w uczelni importu
        # (patrz ImportPlikuPolon.autorzy_niezmatchowani) — bez tego raport
        # wyciekałby autorów innych uczelni współistniejących w bazie.
        import_object = ImportPlikuPolon.objects.get(pk=self.kwargs["pk"])
        unmatched_autor_dyscyplina = import_object.autorzy_niezmatchowani()

        context["unmatched_autor_dyscyplina"] = unmatched_autor_dyscyplina
        context["unmatched_count"] = unmatched_autor_dyscyplina.count()

        return context
