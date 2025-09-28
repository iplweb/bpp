import re

import sentry_sdk
from django.db.models import F
from django.db.models.functions import Coalesce
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django.views.decorators.http import require_POST
from django.views.generic import DetailView, ListView

from .models import PBN_Export_Queue

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin

from django.utils.safestring import mark_safe

from bpp.const import GR_WPROWADZANIE_DANYCH


class PBNExportQueuePermissionMixin(UserPassesTestMixin):
    """Mixin for permission checking - user must be staff or have GR_WPROWADZANIE_DANYCH group"""

    def test_func(self):
        user = self.request.user
        return user.is_staff or user.groups.filter(name=GR_WPROWADZANIE_DANYCH).exists()


class PBNExportQueueListView(
    LoginRequiredMixin, PBNExportQueuePermissionMixin, ListView
):
    """ListView for PBN Export Queue with filtering by success status"""

    model = PBN_Export_Queue
    template_name = "pbn_export_queue/pbn_export_queue_list.html"
    context_object_name = "export_queue_items"
    paginate_by = 25

    def get_queryset(self):
        queryset = super().get_queryset()

        # Annotate with ostatnia_aktualizacja for sorting
        queryset = queryset.annotate(
            ostatnia_aktualizacja_sort=Coalesce(
                F("wysylke_zakonczono"), F("wysylke_podjeto"), F("zamowiono")
            )
        )

        # Filter by zakonczono_pomyslnie if parameter provided
        success_filter = self.request.GET.get("zakonczono_pomyslnie")
        if success_filter == "true":
            queryset = queryset.filter(zakonczono_pomyslnie=True)
        elif success_filter == "false":
            queryset = queryset.filter(zakonczono_pomyslnie=False)
        elif success_filter == "none":
            queryset = queryset.filter(zakonczono_pomyslnie=None)

        # Handle title search
        search_query = self.request.GET.get("q")
        if search_query:
            # Import Q for complex queries
            from django.db.models import Q

            # Search in cached description and original title of the related record
            # We need to get the content types for the models we're interested in
            # Create filters for searching in related models
            # Since we're using GenericForeignKey, we need to filter differently
            # We'll search for the query in the komunikat field which contains publication info
            # and also try to match against object IDs if they exist
            queryset = queryset.filter(Q(komunikat__icontains=search_query))

            # Additionally, we can filter by checking the actual related objects
            # This requires more complex filtering through the generic relation
            matching_ids = []

            # Get all content types that might be in the queue
            for item in queryset.select_related("content_type"):
                if item.rekord_do_wysylki:
                    try:
                        record = item.rekord_do_wysylki
                        # Check if record has title fields
                        if (
                            hasattr(record, "tytul_oryginalny")
                            and record.tytul_oryginalny
                        ):
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

            # If we found matching IDs, filter by them
            if matching_ids:
                queryset = queryset.filter(
                    Q(pk__in=matching_ids) | Q(komunikat__icontains=search_query)
                )

        # Handle sorting
        sort_by = self.request.GET.get(
            "sort", "-ostatnia_aktualizacja"
        )  # Default to newest update first
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


class PBNExportQueueTableView(
    LoginRequiredMixin, PBNExportQueuePermissionMixin, ListView
):
    """Table-only view for HTMX auto-refresh"""

    model = PBN_Export_Queue
    template_name = "pbn_export_queue/pbn_export_queue_table.html"
    context_object_name = "export_queue_items"
    paginate_by = 25

    def get_queryset(self):
        queryset = super().get_queryset()

        # Annotate with ostatnia_aktualizacja for sorting
        queryset = queryset.annotate(
            ostatnia_aktualizacja_sort=Coalesce(
                F("wysylke_zakonczono"), F("wysylke_podjeto"), F("zamowiono")
            )
        )

        # Filter by zakonczono_pomyslnie if parameter provided
        success_filter = self.request.GET.get("zakonczono_pomyslnie")
        if success_filter == "true":
            queryset = queryset.filter(zakonczono_pomyslnie=True)
        elif success_filter == "false":
            queryset = queryset.filter(zakonczono_pomyslnie=False)
        elif success_filter == "none":
            queryset = queryset.filter(zakonczono_pomyslnie=None)

        # Handle title search
        search_query = self.request.GET.get("q")
        if search_query:
            # Import Q for complex queries
            from django.db.models import Q

            # Search in cached description and original title of the related record
            # We need to get the content types for the models we're interested in
            # Create filters for searching in related models
            # Since we're using GenericForeignKey, we need to filter differently
            # We'll search for the query in the komunikat field which contains publication info
            # and also try to match against object IDs if they exist
            queryset = queryset.filter(Q(komunikat__icontains=search_query))

            # Additionally, we can filter by checking the actual related objects
            # This requires more complex filtering through the generic relation
            matching_ids = []

            # Get all content types that might be in the queue
            for item in queryset.select_related("content_type"):
                if item.rekord_do_wysylki:
                    try:
                        record = item.rekord_do_wysylki
                        # Check if record has title fields
                        if (
                            hasattr(record, "tytul_oryginalny")
                            and record.tytul_oryginalny
                        ):
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

            # If we found matching IDs, filter by them
            if matching_ids:
                queryset = queryset.filter(
                    Q(pk__in=matching_ids) | Q(komunikat__icontains=search_query)
                )

        # Handle sorting
        sort_by = self.request.GET.get(
            "sort", "-ostatnia_aktualizacja"
        )  # Default to newest update first
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


class PBNExportQueueDetailView(
    LoginRequiredMixin, PBNExportQueuePermissionMixin, DetailView
):
    """DetailView for PBN Export Queue showing logs and action buttons"""

    model = PBN_Export_Queue
    template_name = "pbn_export_queue/pbn_export_queue_detail.html"
    context_object_name = "export_queue_item"

    def get_queryset(self):
        return super().get_queryset().select_related("zamowil", "content_type")

    def parse_komunikat_links(self, komunikat):
        """Parse the komunikat field to extract and format links"""
        if not komunikat:
            return None

        # Find the SentData link
        sentdata_match = re.search(
            r'href="(/admin/pbn_api/sentdata/\d+/change/)"', komunikat
        )

        links = {}
        if sentdata_match:
            links["sentdata_url"] = sentdata_match.group(1)

            # Try to extract PBN publication ID from the komunikat
            # Looking for patterns like "PBN ID: xxx" or similar
            pbn_match = re.search(r"publication/([a-f0-9-]+)", komunikat)
            if pbn_match:
                links["pbn_uid"] = pbn_match.group(1)
                links["pbn_url"] = (
                    f"https://pbn.nauka.gov.pl/works/publication/{pbn_match.group(1)}"
                )

        # Check if this was successful
        if "Wysłano poprawnie" in komunikat:
            links["success"] = True
        else:
            links["success"] = False

        # Make the komunikat HTML-safe but preserve existing HTML
        links["formatted_komunikat"] = mark_safe(komunikat.replace("\n", "<br>"))

        return links

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # Parse komunikat for links if the record was sent successfully
        if self.object.komunikat:
            context["parsed_links"] = self.parse_komunikat_links(self.object.komunikat)

        # Try to get the related SentData if it exists
        if self.object.zakonczono_pomyslnie:
            try:
                from pbn_api.models.sentdata import SentData

                sent_data = SentData.objects.get(
                    content_type=self.object.content_type,
                    object_id=self.object.object_id,
                )
                context["sent_data"] = sent_data
                if sent_data.pbn_uid_id:
                    # pbn_uid is a ForeignKey to Publication, so we need to use pbn_uid_id or pbn_uid.pbn_uid
                    context["pbn_publication_url"] = (
                        f"https://pbn.nauka.gov.pl/works/publication/{sent_data.pbn_uid_id}"
                    )
            except SentData.DoesNotExist:
                pass

        # Generate admin URL for the record if it exists
        if self.object.rekord_do_wysylki:
            from django.urls import reverse

            content_type = self.object.content_type
            if content_type:
                try:
                    # Generate admin change URL for the specific model
                    admin_url = reverse(
                        f"admin:{content_type.app_label}_{content_type.model}_change",
                        args=[self.object.object_id],
                    )
                    context["record_admin_url"] = admin_url
                except BaseException:
                    # If URL pattern doesn't exist, skip it
                    pass

        return context


@login_required
@require_POST
def resend_to_pbn(request, pk):
    """View to resend an export queue item to PBN (combines prepare and send)"""
    if not (
        request.user.is_staff
        or request.user.groups.filter(name=GR_WPROWADZANIE_DANYCH).exists()
    ):
        messages.error(request, "Brak uprawnień do wykonania tej operacji.")
        return HttpResponseRedirect(
            reverse_lazy("pbn_export_queue:export-queue-detail", args=[pk])
        )

    queue_item = get_object_or_404(PBN_Export_Queue, pk=pk)
    # First prepare for resend
    queue_item.prepare_for_resend(
        user=request.user, message_suffix=f" przez {request.user}"
    )
    # Then trigger the send
    queue_item.sprobuj_wyslac_do_pbn()
    messages.success(request, "Przygotowano i zlecono ponowną wysyłkę do PBN.")
    return HttpResponseRedirect(
        reverse_lazy("pbn_export_queue:export-queue-detail", args=[pk])
    )


# Keep old views for backward compatibility but they won't be used in new UI
@login_required
@require_POST
def prepare_for_resend(request, pk):
    """View to prepare an export queue item for resending - DEPRECATED"""
    if not (
        request.user.is_staff
        or request.user.groups.filter(name=GR_WPROWADZANIE_DANYCH).exists()
    ):
        messages.error(request, "Brak uprawnień do wykonania tej operacji.")
        return HttpResponseRedirect(
            reverse_lazy("pbn_export_queue:export-queue-detail", args=[pk])
        )

    queue_item = get_object_or_404(PBN_Export_Queue, pk=pk)
    queue_item.prepare_for_resend(
        user=request.user, message_suffix=f" przez {request.user}"
    )
    messages.success(request, "Przygotowano rekord do ponownej wysyłki.")
    return HttpResponseRedirect(
        reverse_lazy("pbn_export_queue:export-queue-detail", args=[pk])
    )


@login_required
@require_POST
def try_send_to_pbn(request, pk):
    """View to trigger sending an export queue item to PBN - DEPRECATED"""
    if not (
        request.user.is_staff
        or request.user.groups.filter(name=GR_WPROWADZANIE_DANYCH).exists()
    ):
        messages.error(request, "Brak uprawnień do wykonania tej operacji.")
        return HttpResponseRedirect(
            reverse_lazy("pbn_export_queue:export-queue-detail", args=[pk])
        )

    queue_item = get_object_or_404(PBN_Export_Queue, pk=pk)
    queue_item.sprobuj_wyslac_do_pbn()
    messages.success(request, "Zlecono ponowną wysyłkę do PBN.")
    return HttpResponseRedirect(
        reverse_lazy("pbn_export_queue:export-queue-detail", args=[pk])
    )


@login_required
@require_POST
def resend_all_waiting(request):
    """View to resend all export queue items waiting for authorization"""
    if not (
        request.user.is_staff
        or request.user.groups.filter(name=GR_WPROWADZANIE_DANYCH).exists()
    ):
        messages.error(request, "Brak uprawnień do wykonania tej operacji.")
        return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))

    # Get all items waiting for authorization (retry_after_user_authorised=True)
    waiting_items = PBN_Export_Queue.objects.filter(retry_after_user_authorised=True)
    count = waiting_items.count()

    if count == 0:
        messages.warning(request, "Brak rekordów oczekujących na autoryzację.")
        return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))

    # Process each waiting item
    for queue_item in waiting_items:
        try:
            # Prepare for resend
            queue_item.prepare_for_resend(
                user=request.user,
                message_suffix=f" przez {request.user} (masowa wysyłka oczekujących)",
            )
            # Trigger the send
            queue_item.sprobuj_wyslac_do_pbn()
        except Exception as e:
            # Log the error but continue processing other items
            sentry_sdk.capture_exception(e)
            continue

    messages.success(
        request,
        f"Przygotowano i zlecono ponowną wysyłkę {count} rekordów oczekujących na autoryzację.",
    )
    return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))


@login_required
@require_POST
def resend_all_errors(request):
    """View to resend all export queue items with error status"""
    if not (
        request.user.is_staff
        or request.user.groups.filter(name=GR_WPROWADZANIE_DANYCH).exists()
    ):
        messages.error(request, "Brak uprawnień do wykonania tej operacji.")
        return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))

    # Get all items with errors (zakonczono_pomyslnie=False)
    error_items = PBN_Export_Queue.objects.filter(zakonczono_pomyslnie=False)
    count = error_items.count()

    if count == 0:
        messages.warning(request, "Brak rekordów z błędami do ponownej wysyłki.")
        return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))

    # Process each error item
    for queue_item in error_items:
        try:
            # Prepare for resend
            queue_item.prepare_for_resend(
                user=request.user,
                message_suffix=f" przez {request.user} (masowa wysyłka błędów)",
            )
            # Trigger the send
            queue_item.sprobuj_wyslac_do_pbn()
        except Exception as e:
            # Log the error but continue processing other items
            sentry_sdk.capture_exception(e)
            continue

    messages.success(
        request, f"Przygotowano i zlecono ponowną wysyłkę {count} rekordów z błędami."
    )
    return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))


class PBNExportQueueCountsView(LoginRequiredMixin, PBNExportQueuePermissionMixin, View):
    """JSON view that returns current counts for filter buttons"""

    def get(self, request, *args, **kwargs):
        """Return JSON response with current counts"""
        counts = {
            "total_count": PBN_Export_Queue.objects.count(),
            "success_count": PBN_Export_Queue.objects.filter(
                zakonczono_pomyslnie=True
            ).count(),
            "error_count": PBN_Export_Queue.objects.filter(
                zakonczono_pomyslnie=False
            ).count(),
            "pending_count": PBN_Export_Queue.objects.filter(
                zakonczono_pomyslnie=None
            ).count(),
            "waiting_count": PBN_Export_Queue.objects.filter(
                retry_after_user_authorised=True
            ).count(),
        }
        return JsonResponse(counts)
