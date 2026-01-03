"""Action views for PBN export queue (resend, wake up, etc.)."""

import sys

import rollbar
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import reverse_lazy
from django.views import View
from django.views.decorators.http import require_POST

from bpp.const import GR_WPROWADZANIE_DANYCH
from pbn_export_queue.models import PBN_Export_Queue, RodzajBledu

from .mixins import PBNExportQueuePermissionMixin


def _check_permission(user):
    """Check if user has permission to perform export queue operations."""
    return user.is_staff or user.groups.filter(name=GR_WPROWADZANIE_DANYCH).exists()


@login_required
@require_POST
def delete_from_queue(request, pk):
    """Usuń element z kolejki eksportu PBN"""
    if not _check_permission(request.user):
        messages.error(request, "Brak uprawnień do wykonania tej operacji.")
        return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))

    queue_item = get_object_or_404(PBN_Export_Queue, pk=pk)
    queue_item.delete()
    messages.success(request, "Usunięto element z kolejki.")
    return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))


@login_required
@require_POST
def resend_to_pbn(request, pk):
    """View to resend an export queue item to PBN (combines prepare and send)"""
    if not _check_permission(request.user):
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
    if not _check_permission(request.user):
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
    if not _check_permission(request.user):
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
    if not _check_permission(request.user):
        messages.error(request, "Brak uprawnień do wykonania tej operacji.")
        return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))

    # Get items waiting for authorization (retry_after_user_authorised=True) with limit
    waiting_items = PBN_Export_Queue.objects.filter(retry_after_user_authorised=True)[
        :100
    ]  # Limit do 100

    if not waiting_items:
        messages.warning(request, "Brak rekordów oczekujących na autoryzację.")
        return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))

    # Process each waiting item
    from django.core.cache import cache

    from pbn_export_queue.tasks import LOCK_PREFIX

    count = 0
    skipped = 0
    for queue_item in waiting_items:
        try:
            # Sprawdź czy nie ma już locka dla tego elementu
            lock_key = f"{LOCK_PREFIX}{queue_item.pk}"
            if not cache.get(lock_key):
                # Prepare for resend
                queue_item.prepare_for_resend(
                    user=request.user,
                    message_suffix=f" przez {request.user} (masowa wysyłka oczekujących)",
                )
                # Trigger the send
                queue_item.sprobuj_wyslac_do_pbn()
                count += 1
            else:
                skipped += 1
        except Exception:
            # Log the error but continue processing other items
            rollbar.report_exc_info(sys.exc_info())
            continue

    msg = (
        f"Przygotowano i zlecono ponowną wysyłkę {count} rekordów "
        "oczekujących na autoryzację."
    )
    if skipped > 0:
        msg += f" ({skipped} pominięto - już w trakcie przetwarzania)"

    messages.success(request, msg)
    return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))


@login_required
@require_POST
def resend_all_errors(request):
    """View to resend all export queue items with technical error status"""
    if not _check_permission(request.user):
        messages.error(request, "Brak uprawnień do wykonania tej operacji.")
        return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))

    # Get items with technical errors only (rodzaj_bledu=TECHNICZNY) with limit
    error_items = PBN_Export_Queue.objects.filter(
        zakonczono_pomyslnie=False, rodzaj_bledu=RodzajBledu.TECHNICZNY
    )[:100]  # Limit do 100

    if not error_items:
        messages.warning(
            request, "Brak rekordów z błędami technicznymi do ponownej wysyłki."
        )
        return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))

    # Process each error item
    from django.core.cache import cache

    from pbn_export_queue.tasks import LOCK_PREFIX

    count = 0
    skipped = 0
    for queue_item in error_items:
        try:
            # Sprawdź czy nie ma już locka dla tego elementu
            lock_key = f"{LOCK_PREFIX}{queue_item.pk}"
            if not cache.get(lock_key):
                # Prepare for resend
                queue_item.prepare_for_resend(
                    user=request.user,
                    message_suffix=(
                        f" przez {request.user} (masowa wysyłka błędów technicznych)"
                    ),
                )
                # Trigger the send
                queue_item.sprobuj_wyslac_do_pbn()
                count += 1
            else:
                skipped += 1
        except Exception:
            # Log the error but continue processing other items
            rollbar.report_exc_info(sys.exc_info())
            continue

    msg = (
        f"Przygotowano i zlecono ponowną wysyłkę {count} rekordów z błędami "
        "technicznymi."
    )
    if skipped > 0:
        msg += f" ({skipped} pominięto - już w trakcie przetwarzania)"

    messages.success(request, msg)
    return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))


@login_required
@require_POST
def wake_up_queue(request):
    """View to wake up and start sending all export queue items that were never attempted"""
    if not _check_permission(request.user):
        messages.error(request, "Brak uprawnień do wykonania tej operacji.")
        return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))

    # Get items that were never attempted to send (with limit)
    # (wysylke_podjeto=None means sending was never started)
    never_sent_items = PBN_Export_Queue.objects.filter(
        wysylke_podjeto=None,
        wysylke_zakonczono=None,
    )[:100]  # Limit do 100 rekordów na raz

    if not never_sent_items:
        messages.warning(request, "Brak rekordów oczekujących na pierwszą wysyłkę.")
        return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))

    # Process each never-sent item
    from django.core.cache import cache

    from pbn_export_queue.tasks import LOCK_PREFIX, task_sprobuj_wyslac_do_pbn

    count = 0
    skipped = 0
    for queue_item in never_sent_items:
        try:
            # Sprawdź czy nie ma już locka dla tego elementu
            lock_key = f"{LOCK_PREFIX}{queue_item.pk}"
            if not cache.get(lock_key):
                # Brak locka - można wysyłać
                task_sprobuj_wyslac_do_pbn.delay(queue_item.pk)
                count += 1
            else:
                skipped += 1
        except Exception:
            # Log the error but continue processing other items
            rollbar.report_exc_info(sys.exc_info())
            continue

    msg = f"Obudzono wysyłkę dla {count} rekordów które nigdy nie były wysyłane."
    if skipped > 0:
        msg += f" ({skipped} pominięto - już w trakcie przetwarzania)"

    messages.success(request, msg)
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
                zakonczono_pomyslnie=False, wykluczone=False
            ).count(),
            "pending_count": PBN_Export_Queue.objects.filter(
                zakonczono_pomyslnie=None
            ).count(),
            "waiting_count": PBN_Export_Queue.objects.filter(
                retry_after_user_authorised=True
            ).count(),
            "wykluczone_count": PBN_Export_Queue.objects.filter(
                wykluczone=True
            ).count(),
            "error_techniczny_count": PBN_Export_Queue.objects.filter(
                zakonczono_pomyslnie=False,
                rodzaj_bledu=RodzajBledu.TECHNICZNY,
                wykluczone=False,
            ).count(),
            "error_merytoryczny_count": PBN_Export_Queue.objects.filter(
                zakonczono_pomyslnie=False,
                rodzaj_bledu=RodzajBledu.MERYTORYCZNY,
                wykluczone=False,
            ).count(),
        }
        return JsonResponse(counts)


def _parse_year_value(value):
    """Parse a year string to int, returning None on failure."""
    if not value:
        return None
    try:
        return int(value)
    except ValueError:
        return None


def _filter_by_success_status(queryset, success_filter):
    """Filter queryset by success status."""
    if success_filter == "true":
        return queryset.filter(zakonczono_pomyslnie=True)
    elif success_filter == "false":
        return queryset.filter(zakonczono_pomyslnie=False)
    elif success_filter == "none":
        return queryset.filter(zakonczono_pomyslnie=None)
    return queryset


def _filter_by_error_type(queryset, error_type):
    """Filter queryset by error type."""
    if error_type == "TECH":
        return queryset.filter(
            zakonczono_pomyslnie=False, rodzaj_bledu=RodzajBledu.TECHNICZNY
        )
    elif error_type == "MERYT":
        return queryset.filter(
            zakonczono_pomyslnie=False, rodzaj_bledu=RodzajBledu.MERYTORYCZNY
        )
    return queryset


def _filter_by_year_range(queryset, rok_od_int, rok_do_int):
    """Filter queryset by year range (Python-level filtering due to GenericForeignKey)."""
    if rok_od_int is None and rok_do_int is None:
        return queryset

    matching_ids = []
    for item in queryset.select_related("content_type"):
        rekord = item.rekord_do_wysylki
        if not rekord or not hasattr(rekord, "rok") or rekord.rok is None:
            continue

        rok = rekord.rok
        if rok_od_int is not None and rok < rok_od_int:
            continue
        if rok_do_int is not None and rok > rok_do_int:
            continue
        matching_ids.append(item.pk)

    return queryset.filter(pk__in=matching_ids)


def _get_ids_matching_title(queryset, search_query):
    """Get IDs of items matching search query in title or description."""
    ids_from_title = []
    search_lower = search_query.lower()
    for item in queryset.select_related("content_type"):
        if not item.rekord_do_wysylki:
            continue
        try:
            record = item.rekord_do_wysylki
            if hasattr(record, "tytul_oryginalny") and record.tytul_oryginalny:
                if search_lower in record.tytul_oryginalny.lower():
                    ids_from_title.append(item.pk)
            elif (
                hasattr(record, "opis_bibliograficzny_cache")
                and record.opis_bibliograficzny_cache
            ):
                if search_lower in record.opis_bibliograficzny_cache.lower():
                    ids_from_title.append(item.pk)
        except BaseException:
            pass
    return ids_from_title


def _filter_by_search_query(queryset, search_query):
    """Filter queryset by search query in title and komunikat."""
    if not search_query:
        return queryset

    ids_from_title = _get_ids_matching_title(queryset, search_query)
    ids_from_komunikat = list(
        queryset.filter(komunikat__icontains=search_query).values_list("pk", flat=True)
    )

    all_matching_ids = set(ids_from_title) | set(ids_from_komunikat)
    if all_matching_ids:
        return queryset.filter(pk__in=all_matching_ids)
    return queryset.none()


def _apply_filters_from_post(request):
    """Apply filters from POST data to queryset. Returns filtered queryset."""
    queryset = PBN_Export_Queue.objects.all()

    # Filter by success status
    queryset = _filter_by_success_status(
        queryset, request.POST.get("zakonczono_pomyslnie")
    )

    # Filter by error type
    queryset = _filter_by_error_type(queryset, request.POST.get("rodzaj_bledu"))

    # Filter by year range
    rok_od_int = _parse_year_value(request.POST.get("rok_od", "2022"))
    rok_do_int = _parse_year_value(request.POST.get("rok_do", ""))
    queryset = _filter_by_year_range(queryset, rok_od_int, rok_do_int)

    # Filter by search query
    queryset = _filter_by_search_query(queryset, request.POST.get("q", ""))

    return queryset


@login_required
@require_POST
def resend_filtered(request):
    """View to resend all records matching current filters."""
    if not _check_permission(request.user):
        messages.error(request, "Brak uprawnien do wykonania tej operacji.")
        return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))

    # Apply filters from POST data
    queryset = _apply_filters_from_post(request)

    # Limit to 100 records
    items = list(queryset[:100])

    if not items:
        messages.warning(request, "Brak rekordow pasujacych do filtra.")
        return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))

    # Process each item
    from django.core.cache import cache

    from pbn_export_queue.tasks import LOCK_PREFIX

    count = 0
    skipped = 0
    for queue_item in items:
        try:
            lock_key = f"{LOCK_PREFIX}{queue_item.pk}"
            if not cache.get(lock_key):
                queue_item.prepare_for_resend(
                    user=request.user,
                    message_suffix=f" przez {request.user} (wysylka wyfiltrowanych)",
                )
                queue_item.sprobuj_wyslac_do_pbn()
                count += 1
            else:
                skipped += 1
        except Exception:
            rollbar.report_exc_info(sys.exc_info())
            continue

    msg = f"Przygotowano i zlecono ponowna wysylke {count} rekordow."
    if skipped > 0:
        msg += f" ({skipped} pominieto - juz w trakcie przetwarzania)"
    if len(items) == 100:
        msg += " (limit 100 rekordow)"

    messages.success(request, msg)
    return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))
