"""List views for PBN export queue."""

from django.contrib.auth.mixins import LoginRequiredMixin
from django.db.models import F
from django.db.models.functions import Coalesce
from django.views.generic import ListView

from pbn_export_queue.models import PBN_Export_Queue

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

    def _find_matching_record_ids(self, queryset, search_query):
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
        """Apply search query filter to queryset."""
        search_query = self.request.GET.get("q")
        if not search_query:
            return queryset

        from django.db.models import Q

        # Search in komunikat field which contains publication info
        queryset = queryset.filter(Q(komunikat__icontains=search_query))

        # Additionally filter by checking the actual related objects
        matching_ids = self._find_matching_record_ids(queryset, search_query)

        # If we found matching IDs, filter by them
        if matching_ids:
            queryset = queryset.filter(
                Q(pk__in=matching_ids) | Q(komunikat__icontains=search_query)
            )

        return queryset

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
        queryset = self._apply_search_filter(queryset)
        queryset = self._apply_sorting(queryset)

        return queryset.select_related("zamowil", "content_type")

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context["current_filter"] = self.request.GET.get("zakonczono_pomyslnie", "all")
        context["search_query"] = self.request.GET.get("q", "")
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
        # Add current sort parameter
        context["current_sort"] = self.request.GET.get("sort", "-ostatnia_aktualizacja")
        return context


class PBNExportQueueListView(BasePBNExportQueueListView):
    """ListView for PBN Export Queue with filtering by success status."""

    template_name = "pbn_export_queue/pbn_export_queue_list.html"


class PBNExportQueueTableView(BasePBNExportQueueListView):
    """Table-only view for HTMX auto-refresh."""

    template_name = "pbn_export_queue/pbn_export_queue_table.html"
