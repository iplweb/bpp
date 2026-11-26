import csv

from braces.views import GroupRequiredMixin
from django.contrib import messages
from django.db.models import Count
from django.http import Http404, HttpResponse, QueryDict
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils.functional import cached_property
from django.views import View
from django.views.generic import ListView
from liveops.views import CreateLiveOperationView, RestartView

from bpp.models import Zrodlo
from import_punktacji_zrodel.forms import NowyImportForm, NowyImportScopusForm
from import_punktacji_zrodel.models import (
    RODZAJ_SCOPUS,
    WYBOR_POMIN,
    ImportPunktacjiZrodel,
    WierszImportuPunktacjiZrodel,
)

GROUP_REQUIRED = "wprowadzanie danych"

FILTRY_WYNIKOW = (
    "tylko_do_aktualizacji",
    "tylko_niedopasowane",
    "tylko_duplikaty",
    "tylko_do_rozstrzygniecia",
)


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


class NowyImportScopusView(NowyImportView):
    """Formularz importu CiteScore z eksportu źródeł Scopus (FD#370)."""

    form_class = NowyImportScopusForm
    template_name = "import_punktacji_zrodel/importpunktacjizrodel_form_scopus.html"


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
            qs = qs.filter(zrodlo__isnull=True, kandydaci=[])
        if self.request.GET.get("tylko_duplikaty") == "1":
            qs = qs.filter(is_duplicate=True)
        if self.request.GET.get("tylko_do_rozstrzygniecia") == "1":
            qs = qs.filter(do_rozstrzygniecia=True)
        return qs

    def get_template_names(self):
        if self.parent_object.rodzaj_pliku == RODZAJ_SCOPUS:
            return ["import_punktacji_zrodel/wyniki_scopus.html"]
        return super().get_template_names()

    def _dolacz_kandydatow(self, wiersze):
        """Dokleja do wierszy niejednoznacznych listę kandydatów (nazwa, ISSN,
        wydawca, liczba prac) — jednym zapytaniem na stronę wyników."""
        pks = {pk for w in wiersze for pk in w.kandydaci}
        zrodla = {
            z.pk: z
            for z in Zrodlo.objects.filter(pk__in=pks).annotate(
                liczba_prac=Count("wydawnictwo_ciagle", distinct=True)
            )
        }
        for w in wiersze:
            w.kandydaci_zrodla = [zrodla[pk] for pk in w.kandydaci if pk in zrodla]
            w.wybor = w.dane_z_xls.get("wybor")
            w.pominiety = w.wybor == WYBOR_POMIN

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(object=self.parent_object, **kwargs)
        wszystkie = self.parent_object.get_details_set()
        ctx["total_count"] = wszystkie.count()
        ctx["do_aktualizacji_count"] = wszystkie.filter(wymaga_zmian=True).count()
        ctx["niedopasowane_count"] = self.parent_object.niedopasowane().count()
        ctx["do_rozstrzygniecia_count"] = wszystkie.filter(
            do_rozstrzygniecia=True
        ).count()
        if self.parent_object.rodzaj_pliku == RODZAJ_SCOPUS:
            self._dolacz_kandydatow(
                [w for w in ctx["object_list"] if w.dane_z_xls.get("niejednoznaczny")]
            )
            filtry = self.request.GET.copy()
            ctx["biezacy_adres"] = filtry.urlencode()
            filtry.pop("page", None)
            ctx["filtry"] = filtry.urlencode()
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


class _ImportScopusMixin(GroupRequiredMixin):
    """Import Scopus bieżącego użytkownika (cudzy/nie-Scopus → 404)."""

    group_required = GROUP_REQUIRED

    @cached_property
    def parent_object(self):
        return get_object_or_404(
            ImportPunktacjiZrodel,
            pk=self.kwargs["pk"],
            owner=self.request.user,
            rodzaj_pliku=RODZAJ_SCOPUS,
        )


class WybierzZrodloView(_ImportScopusMixin, View):
    """Decyzja użytkownika dla wiersza niejednoznacznego: jedno ze źródeł-
    kandydatów, „pomiń” albo cofnięcie decyzji. Tylko w podglądzie — po
    zapisie wybór niczego by już nie zmienił."""

    http_method_names = ["post"]

    def post(self, request, *args, **kwargs):
        from import_punktacji_zrodel.core_scopus import NiedozwolonyWybor, ustaw_wybor

        parent = self.parent_object
        wiersz = get_object_or_404(
            WierszImportuPunktacjiZrodel, pk=self.kwargs["wiersz_pk"], parent=parent
        )
        # Powrót na tę samą stronę wyników — przepuszczamy wyłącznie znane
        # parametry filtrów, nic z POST nie trafia do adresu „jak leci”.
        filtry = QueryDict(request.POST.get("filtry", ""))
        zachowane = QueryDict(mutable=True)
        for klucz in (*FILTRY_WYNIKOW, "page"):
            if filtry.get(klucz, "").isdigit():
                zachowane[klucz] = filtry[klucz]
        powrot = reverse(
            "import_punktacji_zrodel:importpunktacjizrodel-results",
            args=[parent.pk],
        )
        if zachowane:
            powrot += "?" + zachowane.urlencode()

        if parent.zapisz_zmiany_do_bazy or not parent.finished_successfully:
            messages.error(
                request, "Źródło można wybrać tylko w gotowym podglądzie importu."
            )
            return redirect(powrot)

        surowy = request.POST.get("zrodlo", "")
        if surowy == "":
            wybor = None
        elif surowy == "pomin":
            wybor = WYBOR_POMIN
        else:
            try:
                wybor = int(surowy)
            except ValueError:
                raise Http404 from None

        try:
            ustaw_wybor(parent, wiersz, wybor)
        except NiedozwolonyWybor as e:
            messages.error(request, str(e))
        return redirect(powrot)


def _bezpieczna_komorka(v) -> str:
    """Wartość do CSV otwieranego w arkuszu: tekst zaczynający się od znaku
    formuły dostaje apostrof (tytuły pochodzą z pliku użytkownika)."""
    s = "" if v is None else str(v)
    if s[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + s
    return s


class NiedopasowaneCsvView(_ImportScopusMixin, View):
    """Lista wierszy pliku bez odpowiednika w BPP — do pobrania."""

    def get(self, request, *args, **kwargs):
        parent = self.parent_object
        response = HttpResponse(content_type="text/csv; charset=utf-8")
        response["Content-Disposition"] = (
            f'attachment; filename="niedopasowane-citescore-{parent.rok}.csv"'
        )
        # BOM: Excel inaczej czyta polskie znaki jako cp1250.
        response.write("\ufeff")
        writer = csv.writer(response, delimiter=";")
        writer.writerow(
            [
                "Nr wiersza",
                "Tytuł",
                "ISSN",
                "E-ISSN",
                "Wydawca",
                "CiteScore",
                "Najwyższy percentyl",
            ]
        )
        for w in parent.niedopasowane():
            d = w.dane_z_xls
            writer.writerow(
                [
                    w.nr_wiersza,
                    *(
                        _bezpieczna_komorka(d.get(k))
                        for k in (
                            "nazwa",
                            "issn",
                            "e_issn",
                            "wydawca",
                            "citescore",
                            "percentyl",
                        )
                    ),
                ]
            )
        return response
