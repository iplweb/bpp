from datetime import timedelta

from cacheops import invalidate_model
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Zrodlo
from django_bpp.version import VERSION

from .models import (
    IgnoredSource,
    NotADuplicate,
    ScanZrodelForDuplicates,
    SourceDuplicateCandidate,
)

# Nieukończony skan starszy niż to = osierocony (martwy worker / zgubiony
# task Celery); NIE blokuje uruchomienia nowego.
SCAN_STALE_AFTER = timedelta(hours=2)


def group_required(*group_names):
    """Decorator sprawdzający czy użytkownik należy do wymaganych grup"""

    def decorator(view_func):
        def wrapper(request, *args, **kwargs):
            if not request.user.is_authenticated:
                messages.error(
                    request, "Musisz być zalogowany, aby uzyskać dostęp do tej strony."
                )
                return redirect("login")

            if request.user.is_superuser:
                return view_func(request, *args, **kwargs)

            user_groups = request.user.groups.values_list("name", flat=True)
            if any(group in user_groups for group in group_names):
                return view_func(request, *args, **kwargs)

            messages.error(request, "Nie masz uprawnień do tej strony.")
            return redirect("bpp:index")

        return wrapper

    return decorator


def latest_completed_scan():
    """Najnowszy ukończony pomyślnie skan (źródło danych dla listy)."""
    return (
        ScanZrodelForDuplicates.objects.filter(
            finished_on__isnull=False, finished_successfully=True, cancelled=False
        )
        .order_by("-finished_on")
        .first()
    )


def active_scan():
    """Nieukończony, NIE-osierocony skan (blokuje uruchomienie kolejnego)."""
    cutoff = timezone.now() - SCAN_STALE_AFTER
    return (
        ScanZrodelForDuplicates.objects.filter(
            finished_on__isnull=True, cancelled=False, created_on__gte=cutoff
        )
        .order_by("-created_on")
        .first()
    )


def visible_candidates(scan, status):
    """Kandydaci skanu w danym statusie, z DYNAMICZNYM wykluczeniem źródeł
    ignorowanych i par oznaczonych jako NotADuplicate (bez re-skanu)."""
    qs = scan.candidates.filter(status=status).select_related(
        "main_zrodlo__pbn_uid", "duplicate_zrodlo__pbn_uid"
    )

    ignored_ids = list(IgnoredSource.objects.values_list("zrodlo_id", flat=True))
    if ignored_ids:
        qs = qs.exclude(main_zrodlo_id__in=ignored_ids).exclude(
            duplicate_zrodlo_id__in=ignored_ids
        )

    # NotADuplicate zapisywany w obie strony; defensywnie wykluczamy oba
    # kierunki pary.
    nd_q = Q()
    for z_id, d_id in NotADuplicate.objects.values_list("zrodlo_id", "duplikat_id"):
        nd_q |= Q(main_zrodlo_id=z_id, duplicate_zrodlo_id=d_id)
        nd_q |= Q(main_zrodlo_id=d_id, duplicate_zrodlo_id=z_id)
    if nd_q:
        qs = qs.exclude(nd_q)

    return qs


@login_required
@group_required(GR_WPROWADZANIE_DANYCH)
def duplicate_sources_view(request):
    """Lista par duplikatów z ostatniego ukończonego skanu."""
    status = request.GET.get("status", SourceDuplicateCandidate.Status.PENDING)
    if status not in SourceDuplicateCandidate.Status.values:
        status = SourceDuplicateCandidate.Status.PENDING

    scan = latest_completed_scan()
    candidates = visible_candidates(scan, status) if scan else []

    running = active_scan()
    context = {
        "scan": scan,
        "candidates": candidates,
        "status": status,
        "status_pending": SourceDuplicateCandidate.Status.PENDING,
        "status_skipped": SourceDuplicateCandidate.Status.SKIPPED,
        "running_scan": running,
        "running_scan_is_mine": bool(running and running.owner_id == request.user.pk),
        "bpp_version": VERSION,
    }
    return render(request, "deduplikator_zrodel/duplicate_sources.html", context)


@login_required
@group_required(GR_WPROWADZANIE_DANYCH)
@require_POST
def start_scan(request):
    """Uruchom skan w tle (django-liveops) i przekieruj na stronę live."""
    if active_scan():
        messages.warning(
            request,
            "Skanowanie jest już w trakcie. Poczekaj na jego zakończenie.",
        )
        return redirect("deduplikator_zrodel:duplicate_sources")

    op = ScanZrodelForDuplicates.objects.create(owner=request.user)
    op.enqueue()
    return redirect(op.get_absolute_url())


@login_required
@group_required(GR_WPROWADZANIE_DANYCH)
@require_POST
def skip_candidate(request):
    """Odłóż kandydata na później (PENDING → SKIPPED)."""
    candidate = get_object_or_404(
        SourceDuplicateCandidate, pk=request.POST.get("candidate_id")
    )
    candidate.status = SourceDuplicateCandidate.Status.SKIPPED
    candidate.save(update_fields=["status"])
    return redirect("deduplikator_zrodel:duplicate_sources")


@login_required
@group_required(GR_WPROWADZANIE_DANYCH)
@require_POST
def unskip_candidate(request):
    """Cofnij odłożenie (SKIPPED → PENDING)."""
    candidate = get_object_or_404(
        SourceDuplicateCandidate, pk=request.POST.get("candidate_id")
    )
    candidate.status = SourceDuplicateCandidate.Status.PENDING
    candidate.save(update_fields=["status"])
    return redirect("deduplikator_zrodel:duplicate_sources")


@login_required
@group_required(GR_WPROWADZANIE_DANYCH)
@require_POST
def reset_skipped(request):
    """Przywróć wszystkie odłożone pary ostatniego skanu do PENDING."""
    scan = latest_completed_scan()
    if scan:
        scan.candidates.filter(status=SourceDuplicateCandidate.Status.SKIPPED).update(
            status=SourceDuplicateCandidate.Status.PENDING
        )
    messages.success(request, "Przywrócono odłożone pary.")
    return redirect("deduplikator_zrodel:duplicate_sources")


@login_required
@group_required(GR_WPROWADZANIE_DANYCH)
@require_POST
def mark_non_duplicate(request):
    """Oznacza parę źródeł jako 'to nie duplikat'"""

    zrodlo_id = request.POST.get("zrodlo_id")
    duplikat_id = request.POST.get("duplikat_id")

    if not zrodlo_id or not duplikat_id:
        messages.error(request, "Brak wymaganych parametrów.")
        return redirect("deduplikator_zrodel:duplicate_sources")

    try:
        zrodlo = get_object_or_404(Zrodlo, pk=zrodlo_id)
        duplikat = get_object_or_404(Zrodlo, pk=duplikat_id)

        with transaction.atomic():
            NotADuplicate.objects.get_or_create(
                zrodlo=zrodlo, duplikat=duplikat, defaults={"created_by": request.user}
            )
            NotADuplicate.objects.get_or_create(
                zrodlo=duplikat, duplikat=zrodlo, defaults={"created_by": request.user}
            )

        invalidate_model(Zrodlo)

        messages.success(
            request,
            f"Oznaczono że '{zrodlo.nazwa}' i '{duplikat.nazwa}' to nie są duplikaty.",
        )

    except Zrodlo.DoesNotExist:
        messages.error(request, "Nie znaleziono źródła o podanym ID.")

    return redirect("deduplikator_zrodel:duplicate_sources")


@login_required
@group_required(GR_WPROWADZANIE_DANYCH)
@require_POST
def ignore_source(request):
    """Dodaje źródło do listy ignorowanych w deduplikacji"""

    zrodlo_id = request.POST.get("zrodlo_id")
    reason = request.POST.get("reason", "")

    if not zrodlo_id:
        messages.error(request, "Brak ID źródła.")
        return redirect("deduplikator_zrodel:duplicate_sources")

    try:
        zrodlo = get_object_or_404(Zrodlo, pk=zrodlo_id)

        IgnoredSource.objects.get_or_create(
            zrodlo=zrodlo, defaults={"reason": reason, "created_by": request.user}
        )

        invalidate_model(Zrodlo)

        messages.success(
            request, f"Źródło '{zrodlo.nazwa}' zostało dodane do listy ignorowanych."
        )

    except Zrodlo.DoesNotExist:
        messages.error(request, "Nie znaleziono źródła o podanym ID.")

    return redirect("deduplikator_zrodel:duplicate_sources")


@login_required
@group_required(GR_WPROWADZANIE_DANYCH)
def download_duplicates_xlsx(request):
    """Pobiera listę duplikatów źródeł (ostatni skan) w formacie XLSX."""
    import datetime
    import sys

    import rollbar
    from django.http import HttpResponse

    from .utils import export_candidates_to_xlsx

    try:
        scan = latest_completed_scan()
        candidates = (
            list(visible_candidates(scan, SourceDuplicateCandidate.Status.PENDING))
            if scan
            else []
        )
        xlsx_content = export_candidates_to_xlsx(candidates, request)

        response = HttpResponse(
            xlsx_content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        filename = f"duplikaty_zrodel_{datetime.date.today().strftime('%Y-%m-%d')}.xlsx"
        response["Content-Disposition"] = f'attachment; filename="{filename}"'
        return response

    except Exception as e:
        rollbar.report_exc_info(sys.exc_info())
        messages.error(request, f"Błąd podczas generowania pliku XLSX: {str(e)}")
        return redirect("deduplikator_zrodel:duplicate_sources")
