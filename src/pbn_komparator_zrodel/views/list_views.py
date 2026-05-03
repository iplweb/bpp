"""Widoki list rozbieżności źródeł i dyscyplin PBN."""

from urllib.parse import quote

from braces.views import GroupRequiredMixin
from django.contrib import messages
from django.db.models import Count, Exists, OuterRef, Q
from django.views.generic import ListView

from bpp.models import Dyscyplina_Naukowa, Wydawnictwo_Ciagle

from ..models import KomparatorZrodelMeta, RozbieznoscZrodlaPBN
from ..utils import (
    cleanup_stale_discrepancies,
    get_brakujace_dyscypliny_pbn,
    is_pbn_journals_data_fresh,
)
from .constants import (
    DEFAULT_ROK_DO,
    DEFAULT_ROK_OD,
    DEFAULT_SORT,
    DYSCYPLINY_VALID_SORT_FIELDS,
    VALID_SORT_FIELDS,
)
from .forms import DyscyplinyFilterForm, FilterForm


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
