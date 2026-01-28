from datetime import timedelta
from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from bpp.const import GR_WPROWADZANIE_DANYCH

from .models import PublicationDuplicateCandidate, PublicationDuplicateScanRun


def group_required(group_name):
    """
    Decorator that requires user to be logged in and belong to a specific group.
    """

    def decorator(view_func):
        @wraps(view_func)
        @login_required
        def wrapper(request, *args, **kwargs):
            if (
                not request.user.is_superuser
                and not request.user.groups.filter(name=group_name).exists()
            ):
                raise PermissionDenied
            return view_func(request, *args, **kwargs)

        return wrapper

    return decorator


def get_latest_completed_scan():
    """Get the most recent completed scan run."""
    return (
        PublicationDuplicateScanRun.objects.filter(
            status=PublicationDuplicateScanRun.Status.COMPLETED
        )
        .order_by("-finished_at")
        .first()
    )


def get_running_scan():
    """Get the currently running scan, if any."""
    return PublicationDuplicateScanRun.objects.filter(
        status=PublicationDuplicateScanRun.Status.RUNNING
    ).first()


@group_required(GR_WPROWADZANIE_DANYCH)
def duplicate_publications_view(request):
    """
    Main view showing duplicate publication candidates.
    """
    running_scan = get_running_scan()
    completed_scan = get_latest_completed_scan()

    # Base context
    context = {
        "running_scan": running_scan,
        "completed_scan": completed_scan,
        "no_scan_available": not completed_scan and not running_scan,
        "pending_candidates_count": 0,
        "candidates": [],
        "page_obj": None,
        # Default form values
        "year_from": 2022,
        "year_to": 2025,
        "ignore_doi": False,
        "ignore_www": False,
        "ignore_isbn": False,
        "ignore_zrodlo": False,
    }

    # If no completed scan, show "run scan first" message
    if not completed_scan:
        if running_scan:
            messages.info(
                request,
                f"Skanowanie w toku: {running_scan.progress_percent}% "
                f"({running_scan.publications_scanned}/"
                f"{running_scan.total_publications_to_scan} publikacji)",
            )
        return render(
            request,
            "deduplikator_publikacji/duplicate_publications.html",
            context,
        )

    # Update form values from completed scan
    context["year_from"] = completed_scan.year_from
    context["year_to"] = completed_scan.year_to
    context["ignore_doi"] = completed_scan.ignore_doi
    context["ignore_www"] = completed_scan.ignore_www
    context["ignore_isbn"] = completed_scan.ignore_isbn
    context["ignore_zrodlo"] = completed_scan.ignore_zrodlo

    # Get pending candidates count
    pending_count = PublicationDuplicateCandidate.objects.filter(
        scan_run=completed_scan,
        status=PublicationDuplicateCandidate.Status.PENDING,
    ).count()
    context["pending_candidates_count"] = pending_count

    # Get candidates with pagination
    candidates_qs = (
        PublicationDuplicateCandidate.objects.filter(
            scan_run=completed_scan,
            status=PublicationDuplicateCandidate.Status.PENDING,
        )
        .select_related(
            "original_content_type",
            "duplicate_content_type",
        )
        .order_by("-similarity_score", "original_title")
    )

    paginator = Paginator(candidates_qs, 25)
    page_number = request.GET.get("page", 1)
    page_obj = paginator.get_page(page_number)

    context["page_obj"] = page_obj
    context["candidates"] = page_obj.object_list

    return render(
        request,
        "deduplikator_publikacji/duplicate_publications.html",
        context,
    )


@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["POST"])
def start_scan_view(request):
    """
    Start a new publication duplicate scan task.
    """
    from .tasks import scan_for_duplicates

    # Check if scan is already running
    if get_running_scan():
        messages.warning(
            request, "Skanowanie jest już w trakcie. Poczekaj na jego zakończenie."
        )
        return redirect("deduplikator_publikacji:duplicate_publications")

    # Get form parameters
    try:
        year_from = int(request.POST.get("year_from", 2022))
        year_to = int(request.POST.get("year_to", 2025))
    except (ValueError, TypeError):
        year_from = 2022
        year_to = 2025

    ignore_doi = request.POST.get("ignore_doi") == "on"
    ignore_www = request.POST.get("ignore_www") == "on"
    ignore_isbn = request.POST.get("ignore_isbn") == "on"
    ignore_zrodlo = request.POST.get("ignore_zrodlo") == "on"

    # Start new scan
    scan_for_duplicates.delay(
        user_id=request.user.pk,
        year_from=year_from,
        year_to=year_to,
        ignore_doi=ignore_doi,
        ignore_www=ignore_www,
        ignore_isbn=ignore_isbn,
        ignore_zrodlo=ignore_zrodlo,
    )

    messages.success(
        request,
        f"Skanowanie publikacji z lat {year_from}-{year_to} zostało uruchomione "
        "w tle. Odśwież stronę za chwilę, aby zobaczyć postęp.",
    )
    return redirect("deduplikator_publikacji:duplicate_publications")


@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["POST"])
def cancel_scan_view(request):
    """
    Cancel the currently running scan.
    """
    from .tasks import cancel_scan

    running_scan = get_running_scan()
    if not running_scan:
        messages.warning(request, "Brak aktywnego skanowania do anulowania.")
        return redirect("deduplikator_publikacji:duplicate_publications")

    cancel_scan.delay(running_scan.pk)
    messages.success(request, "Skanowanie zostało oznaczone do anulowania.")
    return redirect("deduplikator_publikacji:duplicate_publications")


@group_required(GR_WPROWADZANIE_DANYCH)
def scan_status_view(request, scan_id):
    """
    Return scan status as JSON (for AJAX polling).
    """
    try:
        scan_run = PublicationDuplicateScanRun.objects.get(pk=scan_id)

        # Calculate ETA
        eta_seconds = None
        eta_time = None
        elapsed_seconds = None

        if (
            scan_run.status == PublicationDuplicateScanRun.Status.RUNNING
            and scan_run.publications_scanned > 0
            and scan_run.total_publications_to_scan > 0
        ):
            now = timezone.now()
            elapsed = now - scan_run.started_at
            elapsed_seconds = int(elapsed.total_seconds())

            remaining_pubs = (
                scan_run.total_publications_to_scan - scan_run.publications_scanned
            )
            if remaining_pubs > 0:
                time_per_pub = elapsed.total_seconds() / scan_run.publications_scanned
                eta_seconds = int(time_per_pub * remaining_pubs)
                eta_datetime = now + timedelta(seconds=eta_seconds)
                eta_time = eta_datetime.strftime("%H:%M:%S")

        return JsonResponse(
            {
                "id": scan_run.pk,
                "status": scan_run.status,
                "status_display": scan_run.get_status_display(),
                "progress_percent": scan_run.progress_percent,
                "publications_scanned": scan_run.publications_scanned,
                "total_publications_to_scan": scan_run.total_publications_to_scan,
                "duplicates_found": scan_run.duplicates_found,
                "finished": scan_run.status
                in [
                    PublicationDuplicateScanRun.Status.COMPLETED,
                    PublicationDuplicateScanRun.Status.CANCELLED,
                    PublicationDuplicateScanRun.Status.FAILED,
                ],
                "eta_seconds": eta_seconds,
                "eta_time": eta_time,
                "elapsed_seconds": elapsed_seconds,
            }
        )
    except PublicationDuplicateScanRun.DoesNotExist:
        return JsonResponse({"error": "Scan not found"}, status=404)


@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["POST"])
def mark_not_duplicate_view(request):
    """
    Mark a candidate as not a duplicate.
    """
    candidate_id = request.POST.get("candidate_id")

    if not candidate_id:
        messages.error(request, "Brak wymaganego parametru: candidate_id")
        return redirect("deduplikator_publikacji:duplicate_publications")

    try:
        candidate = PublicationDuplicateCandidate.objects.get(pk=candidate_id)
        candidate.status = PublicationDuplicateCandidate.Status.NOT_DUPLICATE
        candidate.reviewed_at = timezone.now()
        candidate.reviewed_by = request.user
        candidate.save()

        messages.success(
            request,
            f"Publikacja oznaczona jako nie-duplikat: {candidate.original_title[:50]}...",
        )
    except PublicationDuplicateCandidate.DoesNotExist:
        messages.error(request, "Nie znaleziono kandydata o podanym ID.")
    except Exception as e:
        messages.error(request, f"Błąd podczas oznaczania: {str(e)}")

    return redirect("deduplikator_publikacji:duplicate_publications")


@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["POST"])
def mark_confirmed_duplicate_view(request):
    """
    Mark a candidate as a confirmed duplicate.
    """
    candidate_id = request.POST.get("candidate_id")

    if not candidate_id:
        messages.error(request, "Brak wymaganego parametru: candidate_id")
        return redirect("deduplikator_publikacji:duplicate_publications")

    try:
        candidate = PublicationDuplicateCandidate.objects.get(pk=candidate_id)
        candidate.status = PublicationDuplicateCandidate.Status.CONFIRMED
        candidate.reviewed_at = timezone.now()
        candidate.reviewed_by = request.user
        candidate.save()

        messages.success(
            request,
            f"Duplikat potwierdzony: {candidate.original_title[:50]}... ↔ "
            f"{candidate.duplicate_title[:50]}...",
        )
    except PublicationDuplicateCandidate.DoesNotExist:
        messages.error(request, "Nie znaleziono kandydata o podanym ID.")
    except Exception as e:
        messages.error(request, f"Błąd podczas oznaczania: {str(e)}")

    return redirect("deduplikator_publikacji:duplicate_publications")
