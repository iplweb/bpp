import logging
from datetime import datetime
from io import BytesIO
from urllib.parse import quote

from braces.views import GroupRequiredMixin
from celery.result import AsyncResult
from django import forms
from django.contrib import messages
from django.db.models import Count, Exists, OuterRef, Q
from django.http import HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View
from django.views.generic import ListView
from openpyxl import Workbook

from bpp.models import Dyscyplina_Naukowa, Wydawnictwo_Ciagle
from bpp.util import worksheet_columns_autosize, worksheet_create_table

from .models import KomparatorZrodelMeta, RozbieznoscZrodlaPBN
from .utils import (
    cleanup_stale_discrepancies,
    get_brakujace_dyscypliny_pbn,
    is_pbn_journals_data_fresh,
)

logger = logging.getLogger(__name__)

CURRENT_YEAR = datetime.now().year
DEFAULT_ROK_OD = 2022
DEFAULT_ROK_DO = 2025
DEFAULT_SORT = "zrodlo__nazwa"
OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE = 20


class FilterForm(forms.Form):
    rok_od = forms.IntegerField(
        min_value=1900,
        max_value=2100,
        required=False,
        widget=forms.NumberInput(
            attrs={"class": "input-group-field", "style": "width: 80px"}
        ),
    )
    rok_do = forms.IntegerField(
        min_value=1900,
        max_value=2100,
        required=False,
        widget=forms.NumberInput(
            attrs={"class": "input-group-field", "style": "width: 80px"}
        ),
    )
    search = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Szukaj w nazwie/ISSN..."}),
    )
    dyscyplina = forms.CharField(
        max_length=20,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Kod dyscypliny..."}),
    )
    tylko_rozbieznosci = forms.BooleanField(required=False, initial=True)
    bez_publikacji = forms.BooleanField(required=False, initial=False)
    bez_publikacji_2022_2025 = forms.BooleanField(required=False, initial=True)

    def clean_rok_od(self):
        return self.cleaned_data.get("rok_od") or DEFAULT_ROK_OD

    def clean_rok_do(self):
        return self.cleaned_data.get("rok_do") or DEFAULT_ROK_DO

    def clean_search(self):
        return self.cleaned_data.get("search") or ""

    def clean_dyscyplina(self):
        return self.cleaned_data.get("dyscyplina") or ""


VALID_SORT_FIELDS = [
    "zrodlo__nazwa",
    "-zrodlo__nazwa",
    "rok",
    "-rok",
    "punkty_bpp",
    "-punkty_bpp",
    "punkty_pbn",
    "-punkty_pbn",
    "updated_at",
    "-updated_at",
]


class RozbieznosciZrodelListView(GroupRequiredMixin, ListView):
    """Lista rozbieżności źródeł."""

    group_required = "wprowadzanie danych"
    model = RozbieznoscZrodlaPBN
    template_name = "pbn_komparator_zrodel/list.html"
    context_object_name = "rozbieznosci"
    paginate_by = 50

    def dispatch(self, request, *args, **kwargs):
        # Automatyczne czyszczenie przestarzałych rozbieżności
        was_cleaned, deleted_count = cleanup_stale_discrepancies()
        if was_cleaned:
            messages.info(
                request,
                f"Lista rozbieżności była starsza niż 7 dni i została automatycznie usunięta "
                f"({deleted_count} rekordów). Uruchom ponownie porównywanie.",
            )
        return super().dispatch(request, *args, **kwargs)

    def get_filter_params(self):
        """Pobiera parametry filtrów z request."""
        # Przy pierwszym wejściu (brak GET params) domyślnie checkboxy zaznaczone
        if not self.request.GET:
            return (
                DEFAULT_ROK_OD,
                DEFAULT_ROK_DO,
                "",
                "",
                True,
                False,
                True,
                DEFAULT_SORT,
            )

        form = FilterForm(self.request.GET)
        if form.is_valid():
            rok_od = form.cleaned_data["rok_od"]
            rok_do = form.cleaned_data["rok_do"]
            search = form.cleaned_data["search"]
            dyscyplina = form.cleaned_data["dyscyplina"]
            # Checkbox: 'on' gdy zaznaczony, brak w GET gdy odznaczony
            tylko_rozbieznosci = "tylko_rozbieznosci" in self.request.GET
            bez_publikacji = "bez_publikacji" in self.request.GET
            bez_publikacji_2022_2025 = "bez_publikacji_2022_2025" in self.request.GET
        else:
            rok_od = DEFAULT_ROK_OD
            rok_do = DEFAULT_ROK_DO
            search = ""
            dyscyplina = ""
            tylko_rozbieznosci = True
            bez_publikacji = False
            bez_publikacji_2022_2025 = True

        sort = self.request.GET.get("sort", DEFAULT_SORT)
        if sort not in VALID_SORT_FIELDS:
            sort = DEFAULT_SORT

        return (
            rok_od,
            rok_do,
            search,
            dyscyplina,
            tylko_rozbieznosci,
            bez_publikacji,
            bez_publikacji_2022_2025,
            sort,
        )

    def get_queryset(self):
        (
            rok_od,
            rok_do,
            search,
            dyscyplina,
            tylko_rozbieznosci,
            bez_publikacji,
            bez_publikacji_2022_2025,
            sort,
        ) = self.get_filter_params()

        queryset = super().get_queryset().select_related("zrodlo", "zrodlo__pbn_uid")

        # Filtr roku
        queryset = queryset.filter(rok__gte=rok_od, rok__lte=rok_do)

        # Filtr wyszukiwania (nazwa, ISSN)
        if search:
            queryset = queryset.filter(
                Q(zrodlo__nazwa__icontains=search)
                | Q(zrodlo__issn__icontains=search)
                | Q(zrodlo__e_issn__icontains=search)
            )

        # Filtr dyscypliny
        if dyscyplina:
            queryset = queryset.filter(
                Q(dyscypliny_bpp__icontains=dyscyplina)
                | Q(dyscypliny_pbn__icontains=dyscyplina)
            )

        # Filtr tylko rozbieżności punktów
        if tylko_rozbieznosci:
            queryset = queryset.filter(ma_rozbieznosc_punktow=True)

        # Filtr tylko źródła z publikacjami
        if bez_publikacji:
            has_publications = Wydawnictwo_Ciagle.objects.filter(
                zrodlo_id=OuterRef("zrodlo_id")
            )
            queryset = queryset.filter(Exists(has_publications))

        # Filtr tylko źródła z publikacjami 2022-2025
        if bez_publikacji_2022_2025:
            has_publications_2022_2025 = Wydawnictwo_Ciagle.objects.filter(
                zrodlo_id=OuterRef("zrodlo_id"), rok__gte=2022, rok__lte=2025
            )
            queryset = queryset.filter(Exists(has_publications_2022_2025))

        # Sortowanie
        queryset = queryset.order_by(sort)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        (
            rok_od,
            rok_do,
            search,
            dyscyplina,
            tylko_rozbieznosci,
            bez_publikacji,
            bez_publikacji_2022_2025,
            sort,
        ) = self.get_filter_params()
        meta = KomparatorZrodelMeta.get_instance()

        # Check PBN journals data freshness
        pbn_data_fresh, pbn_stale_message, pbn_last_download = (
            is_pbn_journals_data_fresh()
        )

        # Optymalizacja: pojedyncze zapytanie zamiast trzech osobnych COUNT
        stats = RozbieznoscZrodlaPBN.objects.aggregate(
            total=Count("id"),
            points=Count("id", filter=Q(ma_rozbieznosc_punktow=True)),
            disciplines=Count("id", filter=Q(ma_rozbieznosc_dyscyplin=True)),
        )

        context.update(
            {
                "meta": meta,
                "rok_od": rok_od,
                "rok_do": rok_do,
                "search": search,
                "dyscyplina": dyscyplina,
                "tylko_rozbieznosci": tylko_rozbieznosci,
                "bez_publikacji": bez_publikacji,
                "bez_publikacji_2022_2025": bez_publikacji_2022_2025,
                "current_sort": sort,
                "total_count": stats["total"],
                "points_count": stats["points"],
                "disciplines_count": stats["disciplines"],
                "pbn_data_fresh": pbn_data_fresh,
                "pbn_stale_message": pbn_stale_message,
                "pbn_last_download": pbn_last_download,
            }
        )

        # Buduj query string dla linków sortowania
        query_params = []
        if rok_od != DEFAULT_ROK_OD:
            query_params.append(f"rok_od={rok_od}")
        if rok_do != DEFAULT_ROK_DO:
            query_params.append(f"rok_do={rok_do}")
        if search:
            query_params.append(f"search={quote(search)}")
        if dyscyplina:
            query_params.append(f"dyscyplina={quote(dyscyplina)}")
        if tylko_rozbieznosci:
            query_params.append("tylko_rozbieznosci=on")
        if bez_publikacji:
            query_params.append("bez_publikacji=on")
        if bez_publikacji_2022_2025:
            query_params.append("bez_publikacji_2022_2025=on")
        context["filter_query_string"] = "&".join(query_params)

        return context


class DyscyplinyFilterForm(forms.Form):
    """Formularz filtrów dla widoku dyscyplin."""

    rok_od = forms.IntegerField(
        min_value=1900,
        max_value=2100,
        required=False,
        widget=forms.NumberInput(
            attrs={"class": "input-group-field", "style": "width: 80px"}
        ),
    )
    rok_do = forms.IntegerField(
        min_value=1900,
        max_value=2100,
        required=False,
        widget=forms.NumberInput(
            attrs={"class": "input-group-field", "style": "width: 80px"}
        ),
    )
    search = forms.CharField(
        max_length=200,
        required=False,
        widget=forms.TextInput(attrs={"placeholder": "Szukaj w nazwie/ISSN..."}),
    )
    tylko_rozbieznosci = forms.BooleanField(required=False, initial=True)
    bez_publikacji = forms.BooleanField(required=False, initial=False)
    bez_publikacji_2022_2025 = forms.BooleanField(required=False, initial=True)
    wyswietlaj_nazwy = forms.BooleanField(required=False, initial=False)

    def clean_rok_od(self):
        return self.cleaned_data.get("rok_od") or DEFAULT_ROK_OD

    def clean_rok_do(self):
        return self.cleaned_data.get("rok_do") or DEFAULT_ROK_DO

    def clean_search(self):
        return self.cleaned_data.get("search") or ""


DYSCYPLINY_VALID_SORT_FIELDS = [
    "zrodlo__nazwa",
    "-zrodlo__nazwa",
    "rok",
    "-rok",
]


class RozbieznosciDyscyplinListView(GroupRequiredMixin, ListView):
    """Lista rozbieżności dyscyplin źródeł - widok dedykowany dla porównania dyscyplin."""

    group_required = "wprowadzanie danych"
    model = RozbieznoscZrodlaPBN
    template_name = "pbn_komparator_zrodel/dyscypliny_list.html"
    context_object_name = "rozbieznosci"
    paginate_by = 50

    def get_filter_params(self):
        """Pobiera parametry filtrów z request."""
        # When form is first loaded (no GET params), use defaults
        if not self.request.GET:
            return (
                DEFAULT_ROK_OD,
                DEFAULT_ROK_DO,
                "",
                True,
                False,
                True,
                False,
                "zrodlo__nazwa",
            )

        form = DyscyplinyFilterForm(self.request.GET)
        if form.is_valid():
            rok_od = form.cleaned_data["rok_od"]
            rok_do = form.cleaned_data["rok_do"]
            search = form.cleaned_data["search"]
            # Checkboxes: 'on' when checked, not present when unchecked
            tylko_rozbieznosci = "tylko_rozbieznosci" in self.request.GET
            bez_publikacji = "bez_publikacji" in self.request.GET
            bez_publikacji_2022_2025 = "bez_publikacji_2022_2025" in self.request.GET
            wyswietlaj_nazwy = "wyswietlaj_nazwy" in self.request.GET
        else:
            rok_od = DEFAULT_ROK_OD
            rok_do = DEFAULT_ROK_DO
            search = ""
            tylko_rozbieznosci = True
            bez_publikacji = False
            bez_publikacji_2022_2025 = True
            wyswietlaj_nazwy = False

        sort = self.request.GET.get("sort", "zrodlo__nazwa")
        if sort not in DYSCYPLINY_VALID_SORT_FIELDS:
            sort = "zrodlo__nazwa"

        return (
            rok_od,
            rok_do,
            search,
            tylko_rozbieznosci,
            bez_publikacji,
            bez_publikacji_2022_2025,
            wyswietlaj_nazwy,
            sort,
        )

    def get_queryset(self):
        (
            rok_od,
            rok_do,
            search,
            tylko_rozbieznosci,
            bez_publikacji,
            bez_publikacji_2022_2025,
            wyswietlaj_nazwy,
            sort,
        ) = self.get_filter_params()

        queryset = super().get_queryset().select_related("zrodlo", "zrodlo__pbn_uid")

        # Filtr roku
        queryset = queryset.filter(rok__gte=rok_od, rok__lte=rok_do)

        # Filtr wyszukiwania (nazwa, ISSN)
        if search:
            queryset = queryset.filter(
                Q(zrodlo__nazwa__icontains=search)
                | Q(zrodlo__issn__icontains=search)
                | Q(zrodlo__e_issn__icontains=search)
            )

        # Filtr tylko rozbieżności
        if tylko_rozbieznosci:
            queryset = queryset.filter(ma_rozbieznosc_dyscyplin=True)

        # Filtr tylko źródła z publikacjami
        if bez_publikacji:
            has_publications = Wydawnictwo_Ciagle.objects.filter(
                zrodlo_id=OuterRef("zrodlo_id")
            )
            queryset = queryset.filter(Exists(has_publications))

        # Filtr tylko źródła z publikacjami 2022-2025
        if bez_publikacji_2022_2025:
            has_publications_2022_2025 = Wydawnictwo_Ciagle.objects.filter(
                zrodlo_id=OuterRef("zrodlo_id"), rok__gte=2022, rok__lte=2025
            )
            queryset = queryset.filter(Exists(has_publications_2022_2025))

        # Sortowanie
        queryset = queryset.order_by(sort)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        (
            rok_od,
            rok_do,
            search,
            tylko_rozbieznosci,
            bez_publikacji,
            bez_publikacji_2022_2025,
            wyswietlaj_nazwy,
            sort,
        ) = self.get_filter_params()
        meta = KomparatorZrodelMeta.get_instance()

        # Check PBN journals data freshness
        pbn_data_fresh, pbn_stale_message, pbn_last_download = (
            is_pbn_journals_data_fresh()
        )

        # Sprawdź brakujące dyscypliny PBN (pobierane z bazy po pobraniu źródeł z PBN)
        brakujace_dyscypliny = get_brakujace_dyscypliny_pbn()

        # Build discipline names cache for display
        dyscypliny_cache = {}
        if wyswietlaj_nazwy:
            dyscypliny_cache = dict(
                Dyscyplina_Naukowa.objects.values_list("kod", "nazwa")
            )

        # Optymalizacja: pojedyncze zapytanie zamiast dwóch osobnych COUNT
        disc_stats = RozbieznoscZrodlaPBN.objects.filter(
            rok__gte=rok_od, rok__lte=rok_do
        ).aggregate(
            total=Count("id"),
            disciplines=Count("id", filter=Q(ma_rozbieznosc_dyscyplin=True)),
        )

        context.update(
            {
                "meta": meta,
                "rok_od": rok_od,
                "rok_do": rok_do,
                "search": search,
                "tylko_rozbieznosci": tylko_rozbieznosci,
                "bez_publikacji": bez_publikacji,
                "bez_publikacji_2022_2025": bez_publikacji_2022_2025,
                "wyswietlaj_nazwy": wyswietlaj_nazwy,
                "dyscypliny_cache": dyscypliny_cache,
                "current_sort": sort,
                "total_count": disc_stats["total"],
                "disciplines_count": disc_stats["disciplines"],
                "pbn_data_fresh": pbn_data_fresh,
                "pbn_stale_message": pbn_stale_message,
                "pbn_last_download": pbn_last_download,
                "brakujace_dyscypliny": brakujace_dyscypliny,
            }
        )

        # Buduj query string dla linków sortowania
        query_params = []
        if rok_od != DEFAULT_ROK_OD:
            query_params.append(f"rok_od={rok_od}")
        if rok_do != DEFAULT_ROK_DO:
            query_params.append(f"rok_do={rok_do}")
        if search:
            query_params.append(f"search={quote(search)}")
        if tylko_rozbieznosci:
            query_params.append("tylko_rozbieznosci=on")
        if bez_publikacji:
            query_params.append("bez_publikacji=on")
        if bez_publikacji_2022_2025:
            query_params.append("bez_publikacji_2022_2025=on")
        if wyswietlaj_nazwy:
            query_params.append("wyswietlaj_nazwy=on")
        context["filter_query_string"] = "&".join(query_params)

        return context


class ExportDyscyplinyXlsxView(GroupRequiredMixin, View):
    """Eksport listy rozbieżności dyscyplin do XLSX."""

    group_required = "wprowadzanie danych"

    def get_filter_params(self):
        """Pobiera parametry filtrów z request."""
        # When no GET params, use defaults
        if not self.request.GET:
            return DEFAULT_ROK_OD, DEFAULT_ROK_DO, "", True, False, True

        form = DyscyplinyFilterForm(self.request.GET)
        if form.is_valid():
            rok_od = form.cleaned_data["rok_od"]
            rok_do = form.cleaned_data["rok_do"]
            search = form.cleaned_data["search"]
            tylko_rozbieznosci = "tylko_rozbieznosci" in self.request.GET
            bez_publikacji = "bez_publikacji" in self.request.GET
            bez_publikacji_2022_2025 = "bez_publikacji_2022_2025" in self.request.GET
            return (
                rok_od,
                rok_do,
                search,
                tylko_rozbieznosci,
                bez_publikacji,
                bez_publikacji_2022_2025,
            )
        return DEFAULT_ROK_OD, DEFAULT_ROK_DO, "", True, False, True

    def get_queryset(self):
        """Buduje queryset z zastosowanymi filtrami."""
        (
            rok_od,
            rok_do,
            search,
            tylko_rozbieznosci,
            bez_publikacji,
            bez_publikacji_2022_2025,
        ) = self.get_filter_params()

        queryset = RozbieznoscZrodlaPBN.objects.select_related(
            "zrodlo", "zrodlo__pbn_uid"
        )
        queryset = queryset.filter(rok__gte=rok_od, rok__lte=rok_do)

        if search:
            queryset = queryset.filter(
                Q(zrodlo__nazwa__icontains=search)
                | Q(zrodlo__issn__icontains=search)
                | Q(zrodlo__e_issn__icontains=search)
            )

        if tylko_rozbieznosci:
            queryset = queryset.filter(ma_rozbieznosc_dyscyplin=True)

        # Filtr tylko źródła z publikacjami
        if bez_publikacji:
            has_publications = Wydawnictwo_Ciagle.objects.filter(
                zrodlo_id=OuterRef("zrodlo_id")
            )
            queryset = queryset.filter(Exists(has_publications))

        # Filtr tylko źródła z publikacjami 2022-2025
        if bez_publikacji_2022_2025:
            has_publications_2022_2025 = Wydawnictwo_Ciagle.objects.filter(
                zrodlo_id=OuterRef("zrodlo_id"), rok__gte=2022, rok__lte=2025
            )
            queryset = queryset.filter(Exists(has_publications_2022_2025))

        return queryset.order_by("zrodlo__nazwa", "rok")

    def get(self, request):
        queryset = self.get_queryset()

        wb = Workbook()
        ws = wb.active
        ws.title = "Rozbieżności dyscyplin"

        # Nagłówki
        headers = [
            "Źródło",
            "ISSN",
            "e-ISSN",
            "Rok",
            "Dyscypliny BPP",
            "Dyscypliny PBN",
            "Rozbieżność",
        ]
        ws.append(headers)

        def format_dyscypliny(value):
            """Add spaces after commas in discipline list."""
            if not value:
                return ""
            return ", ".join(c.strip() for c in value.split(","))

        # Dane
        for rozbieznosc in queryset:
            ws.append(
                [
                    rozbieznosc.zrodlo.nazwa,
                    rozbieznosc.zrodlo.issn or "",
                    rozbieznosc.zrodlo.e_issn or "",
                    rozbieznosc.rok,
                    format_dyscypliny(rozbieznosc.dyscypliny_bpp),
                    format_dyscypliny(rozbieznosc.dyscypliny_pbn),
                    "Tak" if rozbieznosc.ma_rozbieznosc_dyscyplin else "Nie",
                ]
            )

        # Formatowanie
        worksheet_columns_autosize(ws)
        worksheet_create_table(ws, title="RozbieznosciDyscyplin")

        # Odpowiedź HTTP
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        filename = f"rozbieznosci_dyscyplin_pbn_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        virtual_workbook = BytesIO()
        wb.save(virtual_workbook)
        virtual_workbook.seek(0)
        response.write(virtual_workbook.getvalue())

        return response


class PrzebudujRozbieznosciView(GroupRequiredMixin, View):
    """Widok do uruchamiania przebudowy rozbieżności."""

    group_required = "wprowadzanie danych"

    def get(self, request):
        meta = KomparatorZrodelMeta.get_instance()
        is_fresh, stale_message, last_download = is_pbn_journals_data_fresh()

        return render(
            request,
            "pbn_komparator_zrodel/rebuild_confirm.html",
            {
                "meta": meta,
                "current_count": RozbieznoscZrodlaPBN.objects.count(),
                "pbn_data_fresh": is_fresh,
                "pbn_stale_message": stale_message,
                "pbn_last_download": last_download,
            },
        )

    def post(self, request):
        # Sprawdź świeżość danych PBN
        is_fresh, stale_message, _ = is_pbn_journals_data_fresh()
        if not is_fresh:
            messages.error(
                request,
                f"Nie można uruchomić porównywania: {stale_message}. "
                "Najpierw pobierz aktualne dane źródeł z PBN.",
            )
            return HttpResponseRedirect(reverse("pbn_komparator_zrodel:przebuduj"))

        from .tasks import porownaj_zrodla_task

        min_rok = int(request.POST.get("min_rok", 2022))
        clear_existing = request.POST.get("clear_existing") == "on"

        task = porownaj_zrodla_task.delay(
            min_rok=min_rok,
            clear_existing=clear_existing,
        )

        request.session["komparator_zrodel_task_id"] = task.id
        messages.info(request, f"Zadanie porównywania uruchomione. ID: {task.id}")

        return HttpResponseRedirect(
            reverse("pbn_komparator_zrodel:task_status", kwargs={"task_id": task.id})
        )


class AktualizujPojedynczyView(GroupRequiredMixin, View):
    """Aktualizacja pojedynczego źródła."""

    group_required = "wprowadzanie danych"

    def post(self, request, pk):
        from .update_utils import aktualizuj_zrodlo_z_pbn

        typ = request.POST.get("typ", "oba")  # punkty, dyscypliny, oba

        try:
            rozbieznosc = RozbieznoscZrodlaPBN.objects.select_related("zrodlo").get(
                pk=pk
            )
            aktualizuj_zrodlo_z_pbn(
                rozbieznosc.zrodlo,
                rozbieznosc.rok,
                aktualizuj_punkty=(typ in ["punkty", "oba"]),
                aktualizuj_dyscypliny=(typ in ["dyscypliny", "oba"]),
                user=request.user,
            )
            messages.success(
                request,
                f"Zaktualizowano źródło {rozbieznosc.zrodlo.nazwa} za rok {rozbieznosc.rok}",
            )
        except RozbieznoscZrodlaPBN.DoesNotExist:
            messages.error(request, "Nie znaleziono rozbieżności")
        except Exception as e:
            messages.error(request, f"Błąd podczas aktualizacji: {e}")

        # Przekieruj z powrotem do listy z zachowaniem filtrów
        referer = request.META.get("HTTP_REFERER")
        if referer:
            return HttpResponseRedirect(referer)
        return HttpResponseRedirect(reverse("pbn_komparator_zrodel:list"))


class AktualizujWszystkieView(GroupRequiredMixin, View):
    """Aktualizacja wszystkich źródeł z rozbieżnościami."""

    group_required = "wprowadzanie danych"

    def get_filter_params(self):
        """Pobiera parametry filtrów z request."""
        # Przy pierwszym wejściu (brak GET params) domyślnie checkbox zaznaczony
        if not self.request.GET:
            return DEFAULT_ROK_OD, DEFAULT_ROK_DO, "", "", True

        form = FilterForm(self.request.GET)
        if form.is_valid():
            tylko_rozbieznosci = "tylko_rozbieznosci" in self.request.GET
            return (
                form.cleaned_data["rok_od"],
                form.cleaned_data["rok_do"],
                form.cleaned_data["search"],
                form.cleaned_data["dyscyplina"],
                tylko_rozbieznosci,
            )
        return DEFAULT_ROK_OD, DEFAULT_ROK_DO, "", "", True

    def post(self, request):
        from .tasks import aktualizuj_wszystkie_task

        typ = request.POST.get("typ", "oba")
        rok_od, rok_do, search, dyscyplina, tylko_rozbieznosci = (
            self.get_filter_params()
        )

        # Buduj queryset z filtrami
        queryset = RozbieznoscZrodlaPBN.objects.filter(rok__gte=rok_od, rok__lte=rok_do)

        if search:
            queryset = queryset.filter(
                Q(zrodlo__nazwa__icontains=search)
                | Q(zrodlo__issn__icontains=search)
                | Q(zrodlo__e_issn__icontains=search)
            )

        if dyscyplina:
            queryset = queryset.filter(
                Q(dyscypliny_bpp__icontains=dyscyplina)
                | Q(dyscypliny_pbn__icontains=dyscyplina)
            )

        # Filtr tylko rozbieżności punktów (z checkboxa)
        if tylko_rozbieznosci:
            queryset = queryset.filter(ma_rozbieznosc_punktow=True)

        # Dodatkowy filtr na podstawie typu aktualizacji
        if typ == "punkty":
            queryset = queryset.filter(ma_rozbieznosc_punktow=True)
        elif typ == "dyscypliny":
            queryset = queryset.filter(ma_rozbieznosc_dyscyplin=True)

        pks = list(queryset.values_list("pk", flat=True))

        if not pks:
            messages.warning(request, "Brak rekordów do aktualizacji")
            return HttpResponseRedirect(reverse("pbn_komparator_zrodel:list"))

        if len(pks) >= OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE:
            # Uruchom jako task Celery
            task = aktualizuj_wszystkie_task.delay(
                pks=pks,
                typ=typ,
                user_id=request.user.id,
            )
            return HttpResponseRedirect(
                reverse(
                    "pbn_komparator_zrodel:task_status", kwargs={"task_id": task.id}
                )
            )
        else:
            # Wykonaj synchronicznie
            from .update_utils import aktualizuj_wiele_zrodel

            result = aktualizuj_wiele_zrodel(pks, typ=typ, user=request.user)
            if result["errors"]:
                messages.warning(
                    request,
                    f"Zaktualizowano {result['updated']} rekordów. Błędy: {result['errors']}.",
                )
            else:
                messages.success(
                    request, f"Zaktualizowano {result['updated']} rekordów."
                )

            return HttpResponseRedirect(reverse("pbn_komparator_zrodel:list"))


class AktualizujWszystkieDyscyplinyView(GroupRequiredMixin, View):
    """Aktualizacja wszystkich dyscyplin źródeł z rozbieżnościami."""

    group_required = "wprowadzanie danych"

    def get_filter_params(self):
        """Pobiera parametry filtrów z request."""
        if not self.request.GET:
            return DEFAULT_ROK_OD, DEFAULT_ROK_DO, "", True, False, True

        form = DyscyplinyFilterForm(self.request.GET)
        if form.is_valid():
            rok_od = form.cleaned_data["rok_od"]
            rok_do = form.cleaned_data["rok_do"]
            search = form.cleaned_data["search"]
            tylko_rozbieznosci = "tylko_rozbieznosci" in self.request.GET
            bez_publikacji = "bez_publikacji" in self.request.GET
            bez_publikacji_2022_2025 = "bez_publikacji_2022_2025" in self.request.GET
            return (
                rok_od,
                rok_do,
                search,
                tylko_rozbieznosci,
                bez_publikacji,
                bez_publikacji_2022_2025,
            )
        return DEFAULT_ROK_OD, DEFAULT_ROK_DO, "", True, False, True

    def post(self, request):
        from .tasks import aktualizuj_wszystkie_task

        (
            rok_od,
            rok_do,
            search,
            tylko_rozbieznosci,
            bez_publikacji,
            bez_publikacji_2022_2025,
        ) = self.get_filter_params()

        # Buduj queryset z filtrami
        queryset = RozbieznoscZrodlaPBN.objects.filter(rok__gte=rok_od, rok__lte=rok_do)

        if search:
            queryset = queryset.filter(
                Q(zrodlo__nazwa__icontains=search)
                | Q(zrodlo__issn__icontains=search)
                | Q(zrodlo__e_issn__icontains=search)
            )

        # Filtr tylko rozbieżności dyscyplin
        if tylko_rozbieznosci:
            queryset = queryset.filter(ma_rozbieznosc_dyscyplin=True)

        # Filtr tylko źródła z publikacjami
        if bez_publikacji:
            has_publications = Wydawnictwo_Ciagle.objects.filter(
                zrodlo_id=OuterRef("zrodlo_id")
            )
            queryset = queryset.filter(Exists(has_publications))

        # Filtr tylko źródła z publikacjami 2022-2025
        if bez_publikacji_2022_2025:
            has_publications_2022_2025 = Wydawnictwo_Ciagle.objects.filter(
                zrodlo_id=OuterRef("zrodlo_id"), rok__gte=2022, rok__lte=2025
            )
            queryset = queryset.filter(Exists(has_publications_2022_2025))

        # Tylko te z rozbieżnościami dyscyplin
        queryset = queryset.filter(ma_rozbieznosc_dyscyplin=True)

        pks = list(queryset.values_list("pk", flat=True))

        if not pks:
            messages.warning(request, "Brak rekordów do aktualizacji")
            return HttpResponseRedirect(
                reverse("pbn_komparator_zrodel:dyscypliny_list")
            )

        if len(pks) >= OFFLOAD_TASKS_WITH_THIS_ELEMENTS_OR_MORE:
            # Uruchom jako task Celery
            task = aktualizuj_wszystkie_task.delay(
                pks=pks,
                typ="dyscypliny",
                user_id=request.user.id,
            )
            return HttpResponseRedirect(
                reverse(
                    "pbn_komparator_zrodel:task_status", kwargs={"task_id": task.id}
                )
            )
        else:
            # Wykonaj synchronicznie
            from .update_utils import aktualizuj_wiele_zrodel

            result = aktualizuj_wiele_zrodel(pks, typ="dyscypliny", user=request.user)
            if result["errors"]:
                messages.warning(
                    request,
                    f"Zaktualizowano {result['updated']} rekordów. Błędy: {result['errors']}.",
                )
            else:
                messages.success(
                    request, f"Zaktualizowano {result['updated']} rekordów."
                )

            return HttpResponseRedirect(
                reverse("pbn_komparator_zrodel:dyscypliny_list")
            )


class TaskStatusView(GroupRequiredMixin, View):
    """Status zadania z HTMX polling."""

    group_required = "wprowadzanie danych"

    def get(self, request, task_id):
        task = AsyncResult(task_id)
        task_info = task.info if isinstance(task.info, dict) else {}

        context = {
            "task_id": task_id,
            "task_ready": task.ready(),
        }

        if not task.ready():
            context["info"] = task_info
        elif task.failed():
            context["error"] = str(task.info)
        elif task.successful():
            result = task.result or {}
            updated = result.get("updated", 0)
            errors = result.get("errors", 0)
            stats = result.get("stats", {})

            if stats:
                messages.success(
                    request,
                    f"Porównywanie zakończone. Przetworzono: {stats.get('processed', 0)}, "
                    f"rozbieżności punktów: {stats.get('points_discrepancies', 0)}, "
                    f"rozbieżności dyscyplin: {stats.get('discipline_discrepancies', 0)}",
                )
            else:
                messages.success(
                    request,
                    f"Zaktualizowano {updated} rekordów."
                    + (f" Błędy: {errors}." if errors else ""),
                )

            # HTMX redirect
            if request.headers.get("HX-Request"):
                response = HttpResponse(status=200)
                response["HX-Redirect"] = reverse("pbn_komparator_zrodel:list")
                return response
            return redirect("pbn_komparator_zrodel:list")

        # HTMX request: zwróć tylko partial
        if request.headers.get("HX-Request"):
            return render(request, "pbn_komparator_zrodel/_progress.html", context)

        return render(request, "pbn_komparator_zrodel/task_status.html", context)


class ExportXlsxView(GroupRequiredMixin, View):
    """Eksport listy rozbieżności do XLSX."""

    group_required = "wprowadzanie danych"

    def get_filter_params(self):
        """Pobiera parametry filtrów z request (jak w ListView)."""
        # Przy pierwszym wejściu (brak GET params) domyślnie checkbox zaznaczony
        if not self.request.GET:
            return DEFAULT_ROK_OD, DEFAULT_ROK_DO, "", "", True

        form = FilterForm(self.request.GET)
        if form.is_valid():
            tylko_rozbieznosci = "tylko_rozbieznosci" in self.request.GET
            return (
                form.cleaned_data["rok_od"],
                form.cleaned_data["rok_do"],
                form.cleaned_data["search"],
                form.cleaned_data["dyscyplina"],
                tylko_rozbieznosci,
            )
        return DEFAULT_ROK_OD, DEFAULT_ROK_DO, "", "", True

    def get_queryset(self):
        """Buduje queryset z zastosowanymi filtrami."""
        rok_od, rok_do, search, dyscyplina, tylko_rozbieznosci = (
            self.get_filter_params()
        )

        queryset = RozbieznoscZrodlaPBN.objects.select_related(
            "zrodlo", "zrodlo__pbn_uid"
        )
        queryset = queryset.filter(rok__gte=rok_od, rok__lte=rok_do)

        if search:
            queryset = queryset.filter(
                Q(zrodlo__nazwa__icontains=search)
                | Q(zrodlo__issn__icontains=search)
                | Q(zrodlo__e_issn__icontains=search)
            )

        if dyscyplina:
            queryset = queryset.filter(
                Q(dyscypliny_bpp__icontains=dyscyplina)
                | Q(dyscypliny_pbn__icontains=dyscyplina)
            )

        # Filtr tylko rozbieżności punktów
        if tylko_rozbieznosci:
            queryset = queryset.filter(ma_rozbieznosc_punktow=True)

        return queryset.order_by("zrodlo__nazwa", "rok")

    def get(self, request):
        queryset = self.get_queryset()

        wb = Workbook()
        ws = wb.active
        ws.title = "Rozbieżności źródeł PBN"

        # Nagłówki
        headers = [
            "Źródło",
            "ISSN",
            "e-ISSN",
            "Rok",
            "Punkty BPP",
            "Punkty PBN",
            "Różnica punktów",
            "Dyscypliny BPP",
            "Dyscypliny PBN",
            "Rozbieżność punktów",
            "Rozbieżność dyscyplin",
        ]
        ws.append(headers)

        # Dane
        for rozbieznosc in queryset:
            roznica = None
            if (
                rozbieznosc.punkty_bpp is not None
                and rozbieznosc.punkty_pbn is not None
            ):
                roznica = float(rozbieznosc.punkty_bpp - rozbieznosc.punkty_pbn)

            ws.append(
                [
                    rozbieznosc.zrodlo.nazwa,
                    rozbieznosc.zrodlo.issn or "",
                    rozbieznosc.zrodlo.e_issn or "",
                    rozbieznosc.rok,
                    float(rozbieznosc.punkty_bpp) if rozbieznosc.punkty_bpp else None,
                    float(rozbieznosc.punkty_pbn) if rozbieznosc.punkty_pbn else None,
                    roznica,
                    rozbieznosc.dyscypliny_bpp or "",
                    rozbieznosc.dyscypliny_pbn or "",
                    "Tak" if rozbieznosc.ma_rozbieznosc_punktow else "Nie",
                    "Tak" if rozbieznosc.ma_rozbieznosc_dyscyplin else "Nie",
                ]
            )

        # Formatowanie
        worksheet_columns_autosize(ws)
        worksheet_create_table(ws, title="RozbieznosciZrodelPBN")

        # Odpowiedź HTTP
        response = HttpResponse(
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        filename = (
            f"rozbieznosci_zrodel_pbn_{datetime.now().strftime('%Y%m%d_%H%M%S')}.xlsx"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        virtual_workbook = BytesIO()
        wb.save(virtual_workbook)
        virtual_workbook.seek(0)
        response.write(virtual_workbook.getvalue())

        return response
