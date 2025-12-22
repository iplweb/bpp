"""List views for PBN export queue."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F
from django.db.models.functions import Coalesce
from django.views.generic import ListView

from pbn_export_queue.models import PBN_Export_Queue, RodzajBledu

from .mixins import PBNExportQueuePermissionMixin


class BasePBNExportQueueListView(
    LoginRequiredMixin, PBNExportQueuePermissionMixin, ListView
):
    """Base ListView for PBN Export Queue with filtering, searching, and sorting.

    Subclasses only need to specify template_name.
    """

    model = PBN_Export_Queue
    context_object_name = "export_queue_items"
    paginate_by = 25

    def _filter_by_success_status(self, queryset):
        """Filter queryset by zakonczono_pomyslnie parameter."""
        success_filter = self.request.GET.get("zakonczono_pomyslnie")
        if success_filter == "true":
            return queryset.filter(zakonczono_pomyslnie=True)
        elif success_filter == "false":
            return queryset.filter(zakonczono_pomyslnie=False)
        elif success_filter == "none":
            return queryset.filter(zakonczono_pomyslnie=None)
        return queryset

    def _filter_by_error_type(self, queryset):
        """Filter queryset by rodzaj_bledu parameter."""
        error_type = self.request.GET.get("rodzaj_bledu")
        if error_type == "TECH":
            return queryset.filter(
                zakonczono_pomyslnie=False, rodzaj_bledu=RodzajBledu.TECHNICZNY
            )
        elif error_type == "MERYT":
            return queryset.filter(
                zakonczono_pomyslnie=False, rodzaj_bledu=RodzajBledu.MERYTORYCZNY
            )
        return queryset

    def _find_matching_record_ids_by_title(self, queryset, search_query):
        """Find record IDs that match search query in their title fields."""
        matching_ids = []

        for item in queryset.select_related("content_type"):
            if not item.rekord_do_wysylki:
                continue

            try:
                record = item.rekord_do_wysylki
                # Check if record has title fields
                if hasattr(record, "tytul_oryginalny") and record.tytul_oryginalny:
                    if search_query.lower() in record.tytul_oryginalny.lower():
                        matching_ids.append(item.pk)
                elif (
                    hasattr(record, "opis_bibliograficzny_cache")
                    and record.opis_bibliograficzny_cache
                ):
                    if (
                        search_query.lower()
                        in record.opis_bibliograficzny_cache.lower()
                    ):
                        matching_ids.append(item.pk)
            except BaseException:
                pass

        return matching_ids

    def _apply_search_filter(self, queryset):
        """Apply search query filter to queryset.

        Searches in both:
        - komunikat field (error messages)
        - title fields of related record (tytul_oryginalny, opis_bibliograficzny_cache)
        """
        search_query = self.request.GET.get("q")
        if not search_query:
            return queryset

        # Find IDs matching in title
        ids_from_title = self._find_matching_record_ids_by_title(queryset, search_query)

        # Find IDs matching in komunikat (errors)
        ids_from_komunikat = list(
            queryset.filter(komunikat__icontains=search_query).values_list(
                "pk", flat=True
            )
        )

        # UNION both sets
        all_matching_ids = set(ids_from_title) | set(ids_from_komunikat)

        if all_matching_ids:
            return queryset.filter(pk__in=all_matching_ids)
        else:
            return queryset.none()

    def _filter_by_year_range(self, queryset):
        """Filter queryset by year range from rekord_do_wysylki.rok."""
        rok_od = self.request.GET.get("rok_od", "2022")
        rok_do = self.request.GET.get("rok_do", "")

        # Convert to integers, handle empty strings
        try:
            rok_od_int = int(rok_od) if rok_od else None
        except ValueError:
            rok_od_int = None

        try:
            rok_do_int = int(rok_do) if rok_do else None
        except ValueError:
            rok_do_int = None

        if rok_od_int is None and rok_do_int is None:
            return queryset

        # GenericForeignKey requires Python-level filtering
        matching_ids = []
        for item in queryset.select_related("content_type"):
            rekord = item.rekord_do_wysylki
            if not rekord:
                continue
            if not hasattr(rekord, "rok") or rekord.rok is None:
                continue

            rok = rekord.rok
            if rok_od_int is not None and rok < rok_od_int:
                continue
            if rok_do_int is not None and rok > rok_do_int:
                continue
            matching_ids.append(item.pk)

        return queryset.filter(pk__in=matching_ids)

    def _apply_sorting(self, queryset):
        """Apply sorting to queryset based on sort parameter."""
        sort_by = self.request.GET.get("sort", "-ostatnia_aktualizacja")
        allowed_sorts = {
            "pk": "pk",
            "-pk": "-pk",
            "zamowiono": "zamowiono",
            "-zamowiono": "-zamowiono",
            "ostatnia_aktualizacja": "ostatnia_aktualizacja_sort",
            "-ostatnia_aktualizacja": "-ostatnia_aktualizacja_sort",
            "ilosc_prob": "ilosc_prob",
            "-ilosc_prob": "-ilosc_prob",
            "zakonczono_pomyslnie": "zakonczono_pomyslnie",
            "-zakonczono_pomyslnie": "-zakonczono_pomyslnie",
        }
        if sort_by in allowed_sorts:
            queryset = queryset.order_by(allowed_sorts[sort_by])
        return queryset

    def get_queryset(self):
        queryset = super().get_queryset()

        # Annotate with ostatnia_aktualizacja for sorting
        queryset = queryset.annotate(
            ostatnia_aktualizacja_sort=Coalesce(
                F("wysylke_zakonczono"), F("wysylke_podjeto"), F("zamowiono")
            )
        )

        # Apply filters
        queryset = self._filter_by_success_status(queryset)
        queryset = self._filter_by_error_type(queryset)
        queryset = self._filter_by_year_range(queryset)
        queryset = self._apply_search_filter(queryset)
        queryset = self._apply_sorting(queryset)

        return queryset.select_related("zamowil", "content_type")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_filter"] = self.request.GET.get("zakonczono_pomyslnie", "all")
        context["current_error_type"] = self.request.GET.get("rodzaj_bledu", "")
        context["search_query"] = self.request.GET.get("q", "")
        # Year filter values (rok_od defaults to 2022)
        context["rok_od"] = self.request.GET.get("rok_od", "2022")
        context["rok_do"] = self.request.GET.get("rok_do", "")
        # Add count of error records for the resend button
        context["error_count"] = PBN_Export_Queue.objects.filter(
            zakonczono_pomyslnie=False
        ).count()
        # Add count of waiting records for the resend button
        context["waiting_count"] = PBN_Export_Queue.objects.filter(
            retry_after_user_authorised=True
        ).count()
        # Add count of never sent records for the wake up button
        context["never_sent_count"] = PBN_Export_Queue.objects.filter(
            wysylke_podjeto=None,
            wysylke_zakonczono=None,
        ).count()
        # Add counts for filter buttons
        context["total_count"] = PBN_Export_Queue.objects.count()
        context["success_count"] = PBN_Export_Queue.objects.filter(
            zakonczono_pomyslnie=True
        ).count()
        context["pending_count"] = PBN_Export_Queue.objects.filter(
            zakonczono_pomyslnie=None
        ).count()
        # Add counts for error type filter buttons
        context["error_techniczny_count"] = PBN_Export_Queue.objects.filter(
            zakonczono_pomyslnie=False, rodzaj_bledu=RodzajBledu.TECHNICZNY
        ).count()
        context["error_merytoryczny_count"] = PBN_Export_Queue.objects.filter(
            zakonczono_pomyslnie=False, rodzaj_bledu=RodzajBledu.MERYTORYCZNY
        ).count()
        # Add current sort parameter
        context["current_sort"] = self.request.GET.get("sort", "-ostatnia_aktualizacja")
        return context


class PBNExportQueueListView(BasePBNExportQueueListView):
    """ListView for PBN Export Queue with filtering by success status."""

    template_name = "pbn_export_queue/pbn_export_queue_list.html"


class PBNExportQueueTableView(BasePBNExportQueueListView):
    """Table-only view for HTMX auto-refresh."""

    template_name = "pbn_export_queue/pbn_export_queue_table.html"
