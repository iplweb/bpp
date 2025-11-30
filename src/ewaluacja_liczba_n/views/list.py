from decimal import Decimal

from braces.views import GroupRequiredMixin
from django.db.models import Q, Sum
from django.views.generic import ListView

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Autor_Dyscyplina, Dyscyplina_Naukowa
from ewaluacja_common.models import Rodzaj_Autora

from ..models import IloscUdzialowDlaAutoraZaCalosc, IloscUdzialowDlaAutoraZaRok


class AutorzyLiczbaNListView(GroupRequiredMixin, ListView):
    """Lista autorów z liczbą N dla każdej dyscypliny"""

    template_name = "ewaluacja_liczba_n/autorzy_list.html"
    context_object_name = "autorzy_data"
    paginate_by = 50
    group_required = GR_WPROWADZANIE_DANYCH

    def _filter_by_rodzaj_autora(self, queryset, rodzaj_autora_id, rok):
        """Filter queryset by rodzaj_autora (author type)"""
        # Przygotuj filtr dla Autor_Dyscyplina
        ad_filter = {"rodzaj_autora_id": rodzaj_autora_id}

        # Jeśli filtr roku jest ustawiony, użyj dokładnego roku
        # W przeciwnym razie użyj zakresu lat
        if rok:
            ad_filter["rok"] = rok
        else:
            ad_filter["rok__gte"] = 2022
            ad_filter["rok__lte"] = 2025

        # Pobierz pary (autor_id, rok) z danym rodzajem autora
        autorzy_z_rodzajem = (
            Autor_Dyscyplina.objects.filter(**ad_filter)
            .values_list("autor_id", "rok")
            .distinct()
        )

        # Utwórz listę par (autor_id, rok) do filtrowania
        autor_rok_pairs = list(autorzy_z_rodzajem)

        # Filtruj queryset według par (autor_id, rok)
        if autor_rok_pairs:
            # Stwórz warunek Q dla każdej pary
            q_objects = Q()
            for autor_id, ar_rok in autor_rok_pairs:
                q_objects |= Q(autor_id=autor_id, rok=ar_rok)
            queryset = queryset.filter(q_objects)
        else:
            # Jeśli nie ma żadnych pasujących par, zwróć pusty queryset
            queryset = queryset.none()

        return queryset

    def _apply_memory_sorting_for_rodzaj_autora(self, queryset, sort):
        """Apply in-memory sorting for rodzaj_autora field"""
        # Pobierz wszystkie dane i sortuj w pamięci
        items = list(queryset)

        # Pobierz dane Autor_Dyscyplina dla wszystkich elementów
        autorzy_dyscypliny = {
            (ad.autor_id, ad.rok): ad
            for ad in Autor_Dyscyplina.objects.filter(
                autor__in=[item.autor_id for item in items],
                rok__in=[item.rok for item in items],
            ).select_related("rodzaj_autora")
        }

        def get_rodzaj_autora_key(item):
            ad = autorzy_dyscypliny.get((item.autor_id, item.rok))
            if ad and ad.rodzaj_autora:
                return ad.rodzaj_autora.skrot
            return ""

        items.sort(key=get_rodzaj_autora_key, reverse=(sort == "-rodzaj_autora"))

        # Store the sorted list for later use in get_context_data
        self._sorted_items = items
        return items  # Return list, but handle it in get_context_data

    def _apply_filters(self, queryset):
        """Apply all filters from request GET parameters"""
        # Filtrowanie po nazwisku/imieniu autora
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(autor__nazwisko__icontains=search)
                | Q(autor__imiona__icontains=search)
            )

        # Filtrowanie po dyscyplinie
        dyscyplina_id = self.request.GET.get("dyscyplina")
        if dyscyplina_id:
            queryset = queryset.filter(dyscyplina_naukowa_id=dyscyplina_id)

        # Filtrowanie po roku
        rok = self.request.GET.get("rok")
        if rok:
            queryset = queryset.filter(rok=rok)

        # Filtrowanie po rodzaju autora
        rodzaj_autora_id = self.request.GET.get("rodzaj_autora")
        if rodzaj_autora_id:
            queryset = self._filter_by_rodzaj_autora(queryset, rodzaj_autora_id, rok)

        return queryset

    def _get_sort_fields_mapping(self):
        """Return mapping of sort field names to database field lists"""
        return {
            "autor": ["autor__nazwisko", "autor__imiona", "rok"],
            "-autor": ["-autor__nazwisko", "-autor__imiona", "-rok"],
            "rok": ["rok", "autor__nazwisko", "autor__imiona"],
            "-rok": ["-rok", "autor__nazwisko", "autor__imiona"],
            "dyscyplina": [
                "dyscyplina_naukowa__nazwa",
                "autor__nazwisko",
                "autor__imiona",
            ],
            "-dyscyplina": [
                "-dyscyplina_naukowa__nazwa",
                "autor__nazwisko",
                "autor__imiona",
            ],
            "wymiar_etatu": [
                "rok",
                "autor__nazwisko",
                "autor__imiona",
            ],  # Will be sorted in memory
            "-wymiar_etatu": [
                "-rok",
                "autor__nazwisko",
                "autor__imiona",
            ],  # Will be sorted in memory
            "udzialy": ["ilosc_udzialow", "autor__nazwisko", "autor__imiona"],
            "-udzialy": ["-ilosc_udzialow", "autor__nazwisko", "autor__imiona"],
            "monografie": [
                "ilosc_udzialow_monografie",
                "autor__nazwisko",
                "autor__imiona",
            ],
            "-monografie": [
                "-ilosc_udzialow_monografie",
                "autor__nazwisko",
                "autor__imiona",
            ],
            "rodzaj_autora": [
                "autor__nazwisko",
                "autor__imiona",
                "rok",
            ],
            "-rodzaj_autora": [
                "-autor__nazwisko",
                "-autor__imiona",
                "-rok",
            ],
        }

    def _apply_sorting(self, queryset, sort):
        """Apply sorting to queryset based on sort parameter"""
        sort_mapping = self._get_sort_fields_mapping()
        sort_fields = sort_mapping.get(
            sort, ["autor__nazwisko", "autor__imiona", "rok"]
        )
        return queryset.order_by(*sort_fields)

    def get_queryset(self):
        # Pobierz wszystkie udziały dla autorów
        queryset = IloscUdzialowDlaAutoraZaRok.objects.filter(
            rok__gte=2022, rok__lte=2025
        ).select_related(
            "autor",
            "dyscyplina_naukowa",
            "autor_dyscyplina",
            "autor_dyscyplina__rodzaj_autora",
        )

        # Apply filters
        queryset = self._apply_filters(queryset)

        # Apply sorting
        sort = self.request.GET.get("sort", "autor")
        queryset = self._apply_sorting(queryset, sort)

        # Sortowanie w pamięci dla rodzaj_autora
        if sort in ["rodzaj_autora", "-rodzaj_autora"]:
            return self._apply_memory_sorting_for_rodzaj_autora(queryset, sort)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Pobierz ID dyscyplin które mają faktyczne dane
        dyscypliny_z_danymi = (
            IloscUdzialowDlaAutoraZaRok.objects.filter(rok__gte=2022, rok__lte=2025)
            .values_list("dyscyplina_naukowa_id", flat=True)
            .distinct()
        )

        # Filtruj tylko te dyscypliny które mają dane
        context["dyscypliny"] = Dyscyplina_Naukowa.objects.filter(
            pk__in=dyscypliny_z_danymi, widoczna=True
        ).order_by("nazwa")

        # Pobierz tylko lata które faktycznie są w bazie
        lata_z_danymi = (
            IloscUdzialowDlaAutoraZaRok.objects.filter(rok__gte=2022, rok__lte=2025)
            .values_list("rok", flat=True)
            .distinct()
            .order_by("rok")
        )

        context["lata"] = list(lata_z_danymi)

        # Pobierz wszystkie rodzaje autorów
        context["rodzaje_autorow"] = Rodzaj_Autora.objects.all().order_by("sort")

        # Aktualne filtry i sortowanie
        context["selected_dyscyplina"] = self.request.GET.get("dyscyplina", "")
        context["selected_rok"] = self.request.GET.get("rok", "")
        context["selected_rodzaj_autora"] = self.request.GET.get("rodzaj_autora", "")
        context["search"] = self.request.GET.get("search", "")
        context["current_sort"] = self.request.GET.get("sort", "autor")

        # Oblicz sumy dla przefiltrowanych danych (przed paginacją)
        queryset_for_sum = self.get_queryset()

        # Handle both queryset and list cases
        if hasattr(self, "_sorted_items") and isinstance(queryset_for_sum, list):
            # We have a sorted list from memory sorting
            context["suma_udzialow"] = sum(
                float(item.ilosc_udzialow) for item in queryset_for_sum
            )
            context["suma_monografie"] = sum(
                float(item.ilosc_udzialow_monografie) for item in queryset_for_sum
            )
            context["total_count"] = len(queryset_for_sum)
        else:
            # Normal queryset case
            sums = queryset_for_sum.aggregate(
                suma_udzialow=Sum("ilosc_udzialow"),
                suma_monografie=Sum("ilosc_udzialow_monografie"),
            )
            context["suma_udzialow"] = sums["suma_udzialow"] or 0
            context["suma_monografie"] = sums["suma_monografie"] or 0
            context["total_count"] = queryset_for_sum.count()

        # Add Autor_Dyscyplina data for each item
        for item in context["object_list"]:
            if item.autor_dyscyplina:
                item.wymiar_etatu = item.autor_dyscyplina.wymiar_etatu

                # Calculate wymiar_etatu_dla_dyscypliny
                if item.autor_dyscyplina.wymiar_etatu:
                    if (
                        item.dyscyplina_naukowa_id
                        == item.autor_dyscyplina.dyscyplina_naukowa_id
                    ):
                        item.wymiar_etatu_dla_dyscypliny = (
                            item.autor_dyscyplina.wymiar_etatu
                            * (item.autor_dyscyplina.procent_dyscypliny or Decimal("0"))
                            / Decimal("100")
                        )
                    elif (
                        item.dyscyplina_naukowa_id
                        == item.autor_dyscyplina.subdyscyplina_naukowa_id
                    ):
                        item.wymiar_etatu_dla_dyscypliny = (
                            item.autor_dyscyplina.wymiar_etatu
                            * (
                                item.autor_dyscyplina.procent_subdyscypliny
                                or Decimal("0")
                            )
                            / Decimal("100")
                        )
                    else:
                        item.wymiar_etatu_dla_dyscypliny = None
                else:
                    item.wymiar_etatu_dla_dyscypliny = None

                # Dodaj rodzaj autora
                item.rodzaj_autora = item.autor_dyscyplina.rodzaj_autora
            else:
                item.wymiar_etatu = None
                item.wymiar_etatu_dla_dyscypliny = None
                item.rodzaj_autora = None

        # Oblicz sumy dla bieżącej strony
        page_suma_udzialow = 0
        page_suma_monografie = 0
        for item in context["object_list"]:
            page_suma_udzialow += float(item.ilosc_udzialow)
            page_suma_monografie += float(item.ilosc_udzialow_monografie)

        context["page_suma_udzialow"] = page_suma_udzialow
        context["page_suma_monografie"] = page_suma_monografie

        return context


class UdzialyZaCaloscListView(GroupRequiredMixin, ListView):
    """Lista udziałów za cały okres ewaluacji"""

    template_name = "ewaluacja_liczba_n/udzialy_za_calosc_list.html"
    context_object_name = "udzialy_data"
    paginate_by = 50
    group_required = GR_WPROWADZANIE_DANYCH

    def get_queryset(self):
        # Pobierz wszystkie udziały za cały okres
        queryset = IloscUdzialowDlaAutoraZaCalosc.objects.all().select_related(
            "autor", "dyscyplina_naukowa", "rodzaj_autora"
        )

        # Filtrowanie po nazwisku/imieniu autora
        search = self.request.GET.get("search")
        if search:
            queryset = queryset.filter(
                Q(autor__nazwisko__icontains=search)
                | Q(autor__imiona__icontains=search)
            )

        # Filtrowanie po dyscyplinie
        dyscyplina_id = self.request.GET.get("dyscyplina")
        if dyscyplina_id:
            queryset = queryset.filter(dyscyplina_naukowa_id=dyscyplina_id)

        # Filtrowanie po rodzaju autora
        # Model IloscUdzialowDlaAutoraZaCalosc ma już pole rodzaj_autora
        rodzaj_autora_id = self.request.GET.get("rodzaj_autora")
        if rodzaj_autora_id:
            queryset = queryset.filter(rodzaj_autora_id=rodzaj_autora_id)

        # Sortowanie
        sort = self.request.GET.get("sort", "autor")

        # Mapowanie pól sortowania
        sort_mapping = {
            "autor": ["autor__nazwisko", "autor__imiona"],
            "-autor": ["-autor__nazwisko", "-autor__imiona"],
            "dyscyplina": ["dyscyplina_naukowa__nazwa"],
            "-dyscyplina": ["-dyscyplina_naukowa__nazwa"],
            "udzialy": ["ilosc_udzialow"],
            "-udzialy": ["-ilosc_udzialow"],
            "monografie": ["ilosc_udzialow_monografie"],
            "-monografie": ["-ilosc_udzialow_monografie"],
        }

        # Zastosuj sortowanie
        sort_fields = sort_mapping.get(sort, ["autor__nazwisko", "autor__imiona"])
        queryset = queryset.order_by(*sort_fields)

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Pobierz ID dyscyplin które mają faktyczne dane
        dyscypliny_z_danymi = IloscUdzialowDlaAutoraZaCalosc.objects.values_list(
            "dyscyplina_naukowa_id", flat=True
        ).distinct()

        # Filtruj tylko te dyscypliny które mają dane
        context["dyscypliny"] = Dyscyplina_Naukowa.objects.filter(
            pk__in=dyscypliny_z_danymi, widoczna=True
        ).order_by("nazwa")

        # Pobierz wszystkie rodzaje autorów
        context["rodzaje_autorow"] = Rodzaj_Autora.objects.all().order_by("sort")

        # Aktualne filtry i sortowanie
        context["selected_dyscyplina"] = self.request.GET.get("dyscyplina", "")
        context["selected_rodzaj_autora"] = self.request.GET.get("rodzaj_autora", "")
        context["search"] = self.request.GET.get("search", "")
        context["current_sort"] = self.request.GET.get("sort", "autor")

        # Oblicz sumy dla przefiltrowanych danych (przed paginacją)
        queryset_for_sum = self.get_queryset()
        sums = queryset_for_sum.aggregate(
            suma_udzialow=Sum("ilosc_udzialow"),
            suma_monografie=Sum("ilosc_udzialow_monografie"),
        )
        context["suma_udzialow"] = sums["suma_udzialow"] or 0
        context["suma_monografie"] = sums["suma_monografie"] or 0
        context["total_count"] = queryset_for_sum.count()

        # Oblicz sumy dla bieżącej strony
        page_suma_udzialow = 0
        page_suma_monografie = 0
        for item in context["object_list"]:
            page_suma_udzialow += float(item.ilosc_udzialow or 0)
            page_suma_monografie += float(item.ilosc_udzialow_monografie or 0)

        context["page_suma_udzialow"] = page_suma_udzialow
        context["page_suma_monografie"] = page_suma_monografie

        return context
