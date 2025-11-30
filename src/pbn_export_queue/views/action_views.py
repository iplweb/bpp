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
from pbn_export_queue.models import PBN_Export_Queue

from .mixins import PBNExportQueuePermissionMixin


def _check_permission(user):
    """Check if user has permission to perform export queue operations."""
    return user.is_staff or user.groups.filter(name=GR_WPROWADZANIE_DANYCH).exists()


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
    """View to resend all export queue items with error status"""
    if not _check_permission(request.user):
        messages.error(request, "Brak uprawnień do wykonania tej operacji.")
        return HttpResponseRedirect(reverse_lazy("pbn_export_queue:export-queue-list"))

    # Get items with errors (zakonczono_pomyslnie=False) with limit
    error_items = PBN_Export_Queue.objects.filter(zakonczono_pomyslnie=False)[
        :100
    ]  # Limit do 100

    if not error_items:
        messages.warning(request, "Brak rekordów z błędami do ponownej wysyłki.")
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
                    message_suffix=f" przez {request.user} (masowa wysyłka błędów)",
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

    msg = f"Przygotowano i zlecono ponowną wysyłkę {count} rekordów z błędami."
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
