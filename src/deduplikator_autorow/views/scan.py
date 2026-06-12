"""Scan-task lifecycle views (start / cancel / status)."""

from datetime import timedelta

from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from bpp.const import GR_WPROWADZANIE_DANYCH
from pbn_downloader_app.freshness import is_pbn_people_data_fresh

from ..models import DuplicateScanRun
from .helpers import get_running_scan, group_required


@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["POST"])
def start_scan_view(request):
    """
    Start a new duplicate scan task.
    """
    from ..tasks import scan_for_duplicates

    # Check if PBN people data is fresh
    pbn_data_fresh, pbn_stale_message, _ = is_pbn_people_data_fresh()
    if not pbn_data_fresh:
        messages.warning(
            request,
            f"Uruchamiasz skanowanie na nieaktualnych danych PBN: "
            f"{pbn_stale_message}. Wyniki mogą być nieaktualne.",
        )

    # Check if scan is already running
    if get_running_scan():
        messages.warning(
            request, "Skanowanie jest już w trakcie. Poczekaj na jego zakończenie."
        )
        return redirect("deduplikator_autorow:duplicate_authors")

    # Start new scan
    scan_for_duplicates.delay(user_id=request.user.pk)
    messages.success(
        request,
        "Skanowanie duplikatów zostało uruchomione w tle. "
        "Odśwież stronę za chwilę, aby zobaczyć postęp.",
    )
    return redirect("deduplikator_autorow:duplicate_authors")


@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["POST"])
def cancel_scan_view(request):
    """
    Cancel the currently running scan.
    """
    from ..tasks import cancel_scan

    running_scan = get_running_scan()
    if not running_scan:
        messages.warning(request, "Brak aktywnego skanowania do anulowania.")
        return redirect("deduplikator_autorow:duplicate_authors")

    cancel_scan.delay(running_scan.pk)
    messages.success(request, "Skanowanie zostało oznaczone do anulowania.")
    return redirect("deduplikator_autorow:duplicate_authors")


@group_required(GR_WPROWADZANIE_DANYCH)
def scan_status_view(request, scan_id):
    """
    Return scan status as JSON (for AJAX polling).
    """
    try:
        scan_run = DuplicateScanRun.objects.get(pk=scan_id)

        # Calculate ETA
        eta_seconds = None
        eta_time = None
        elapsed_seconds = None

        if (
            scan_run.status == DuplicateScanRun.Status.RUNNING
            and scan_run.authors_scanned > 0
            and scan_run.total_authors_to_scan > 0
        ):
            now = timezone.now()
            elapsed = now - scan_run.started_at
            elapsed_seconds = int(elapsed.total_seconds())

            remaining_authors = (
                scan_run.total_authors_to_scan - scan_run.authors_scanned
            )
            if remaining_authors > 0:
                time_per_author = elapsed.total_seconds() / scan_run.authors_scanned
                eta_seconds = int(time_per_author * remaining_authors)
                eta_datetime = now + timedelta(seconds=eta_seconds)
                eta_time = eta_datetime.strftime("%H:%M:%S")

        return JsonResponse(
            {
                "id": scan_run.pk,
                "status": scan_run.status,
                "status_display": scan_run.get_status_display(),
                "progress_percent": scan_run.progress_percent,
                "authors_scanned": scan_run.authors_scanned,
                "total_authors_to_scan": scan_run.total_authors_to_scan,
                "duplicates_found": scan_run.duplicates_found,
                "finished": scan_run.status
                in [
                    DuplicateScanRun.Status.COMPLETED,
                    DuplicateScanRun.Status.PARTIAL_COMPLETED,
                    DuplicateScanRun.Status.CANCELLED,
                    DuplicateScanRun.Status.FAILED,
                ],
                "eta_seconds": eta_seconds,
                "eta_time": eta_time,
                "elapsed_seconds": elapsed_seconds,
            }
        )
    except DuplicateScanRun.DoesNotExist:
        return JsonResponse({"error": "Scan not found"}, status=404)
