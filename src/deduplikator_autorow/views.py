import sys
import traceback
from datetime import timedelta
from functools import wraps

import rollbar
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Autor
from bpp.models.cache import Rekord
from pbn_api.models import Scientist
from pbn_downloader_app.models import PbnDownloadTask

from .models import (
    DuplicateCandidate,
    DuplicateScanRun,
    IgnoredAuthor,
    LogScalania,
    NotADuplicate,
)
from .utils import (
    count_authors_with_lastname,
    export_duplicates_to_xlsx,
    scal_autorow,
    search_author_by_lastname,
    znajdz_pierwszego_autora_z_duplikatami,
)

# Minimalny próg pewności do wyświetlania duplikatów
# Duplikaty z pewnością poniżej tego progu nie będą pokazywane
MIN_PEWNOSC_DO_WYSWIETLENIA = 50


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


def _get_excluded_authors_from_session(request):
    """Get excluded authors from session as Scientist objects."""
    skipped_authors_ids = request.session.get("skipped_authors", [])
    if skipped_authors_ids:
        return list(Scientist.objects.filter(pk__in=skipped_authors_ids))
    return []


def _handle_search_request(search_lastname):
    """Handle search request and return scientist and count."""
    scientist = search_author_by_lastname(search_lastname, excluded_authors=None)
    search_results_count = count_authors_with_lastname(search_lastname)
    return scientist, search_results_count


def _clear_navigation_session(request):
    """Clear skipped authors and navigation history from session."""
    if "skipped_authors" in request.session:
        del request.session["skipped_authors"]
    if "navigation_history" in request.session:
        del request.session["navigation_history"]
    request.session.modified = True


def _handle_go_previous(request, navigation_history, excluded_authors):
    """Handle 'go previous' navigation action."""
    if not navigation_history:
        return znajdz_pierwszego_autora_z_duplikatami(excluded_authors)

    previous_scientist_id = navigation_history.pop()
    request.session["navigation_history"] = navigation_history
    request.session.modified = True

    try:
        return Scientist.objects.get(pk=previous_scientist_id)
    except Scientist.DoesNotExist:
        return znajdz_pierwszego_autora_z_duplikatami(excluded_authors)


def _handle_skip_current(request, scientist, excluded_authors):
    """Handle 'skip current' navigation action."""
    if not scientist:
        return scientist

    # Save to navigation history
    if "navigation_history" not in request.session:
        request.session["navigation_history"] = []
    request.session["navigation_history"].append(scientist.pk)

    # Add to skipped
    if "skipped_authors" not in request.session:
        request.session["skipped_authors"] = []
    if scientist.pk not in request.session["skipped_authors"]:
        request.session["skipped_authors"].append(scientist.pk)
    request.session.modified = True

    # Find next author
    excluded_authors.append(scientist)
    return znajdz_pierwszego_autora_z_duplikatami(excluded_authors)


def _calculate_year_range(queryset):
    """Calculate year range from a queryset with 'rok' field."""
    lata = queryset.filter(rok__isnull=False).values_list("rok", flat=True)
    if not lata:
        return None

    min_rok = min(lata)
    max_rok = max(lata)
    if min_rok == max_rok:
        return str(min_rok)
    return f"{min_rok}-{max_rok}"


def _build_duplicate_publication_data(autor, metryka):
    """Build publication data for a duplicate author."""
    publikacje = Rekord.objects.prace_autora(autor)[:500]
    publikacje_count = Rekord.objects.prace_autora(autor).count()
    year_range = _calculate_year_range(Rekord.objects.prace_autora(autor))

    return {
        "autor": autor,
        "publikacje": publikacje,
        "publikacje_count": publikacje_count,
        "publikacje_year_range": year_range,
    }


def _add_dyscypliny_to_duplicates(duplikaty_z_publikacjami):
    """Add discipline information to duplicate authors."""
    from bpp.models import Autor_Dyscyplina

    for duplikat_data in duplikaty_z_publikacjami:
        duplikat_data["dyscypliny"] = (
            Autor_Dyscyplina.objects.filter(
                autor=duplikat_data["autor"], rok__gte=2022, rok__lte=2025
            )
            .select_related("dyscyplina_naukowa", "subdyscyplina_naukowa")
            .order_by("rok")
        )


def _build_context_from_candidate(candidate, glowny_autor):
    """Build publication data for a duplicate from stored DuplicateCandidate."""
    publikacje = Rekord.objects.prace_autora(candidate.duplicate_autor)[:500]
    publikacje_count = candidate.duplicate_publications_count
    year_range = _calculate_year_range(
        Rekord.objects.prace_autora(candidate.duplicate_autor)
    )

    return {
        "autor": candidate.duplicate_autor,
        "publikacje": publikacje,
        "publikacje_count": publikacje_count,
        "publikacje_year_range": year_range,
        "analiza": {
            "autor": candidate.duplicate_autor,
            "pewnosc": candidate.confidence_score,
            "powody_podobienstwa": candidate.reasons,
        },
        "candidate_id": candidate.pk,  # For marking as not duplicate
    }


@group_required(GR_WPROWADZANIE_DANYCH)
def duplicate_authors_view(request):  # noqa: C901
    """
    Widok pokazujący główny rekord autora wraz z możliwymi duplikatami
    i ich publikacjami (do 500 na duplikat).

    Uses pre-computed duplicates from DuplicateCandidate table.
    """
    from bpp.models import Autor_Dyscyplina

    # Get scan status
    running_scan = get_running_scan()
    completed_scan = get_latest_completed_scan()

    # Common context
    not_duplicate_count = NotADuplicate.objects.count()
    ignored_authors_count = IgnoredAuthor.objects.count()
    latest_pbn_download = PbnDownloadTask.get_latest_task()

    recent_merges = (
        LogScalania.objects.filter(created_by=request.user)
        .select_related("main_autor", "dyscyplina_before", "dyscyplina_after")
        .order_by("-created_on")[:10]
    )

    # Base context for all scenarios
    context = {
        "scientist": None,
        "glowny_autor": None,
        "latest_pbn_download": latest_pbn_download,
        "duplikaty_z_publikacjami": [],
        "analiza": None,
        "has_skipped_authors": False,
        "has_previous_authors": False,
        "total_authors_with_duplicates": 0,
        "not_duplicate_count": not_duplicate_count,
        "ignored_authors_count": ignored_authors_count,
        "search_lastname": "",
        "search_results_count": None,
        "recent_merges": recent_merges,
        # New scan-related context
        "running_scan": running_scan,
        "completed_scan": completed_scan,
        "no_scan_available": not completed_scan and not running_scan,
        "pending_candidates_count": 0,
        # Navigation
        "skip_count": 0,
    }

    # If no completed scan, show "run scan first" message
    if not completed_scan:
        if running_scan:
            messages.info(
                request,
                f"Skanowanie w toku: {running_scan.progress_percent}% "
                f"({running_scan.authors_scanned}/{running_scan.total_authors_to_scan} autorów)",
            )
        return render(request, "deduplikator_autorow/duplicate_authors.html", context)

    # Count pending candidates
    pending_count = DuplicateCandidate.objects.filter(
        scan_run=completed_scan,
        status=DuplicateCandidate.Status.PENDING,
    ).count()
    context["pending_candidates_count"] = pending_count
    context["total_authors_with_duplicates"] = pending_count

    # Handle search by lastname
    search_lastname = request.GET.get("search_lastname", "").strip()
    context["search_lastname"] = search_lastname

    if search_lastname:
        # Search within stored candidates
        candidates = (
            DuplicateCandidate.objects.filter(
                scan_run=completed_scan,
                status=DuplicateCandidate.Status.PENDING,
                main_autor__nazwisko__icontains=search_lastname,
            )
            .select_related("main_autor", "duplicate_autor")
            .order_by("-priority", "-confidence_score")
        )

        context["search_results_count"] = (
            candidates.values("main_autor").distinct().count()
        )

        if candidates.exists():
            first_candidate = candidates.first()
            glowny_autor = first_candidate.main_autor
            candidates_for_author = candidates.filter(main_autor=glowny_autor)
        else:
            glowny_autor = None
            candidates_for_author = DuplicateCandidate.objects.none()
    else:
        # Handle navigation - use skip_count as offset
        try:
            skip_count = int(request.GET.get("skip_count", 0))
        except (ValueError, TypeError):
            skip_count = 0

        # Get next author with pending duplicates using offset
        glowny_autor, candidates_for_author, skip_count = _get_next_candidate_group(
            completed_scan, skip_count=skip_count
        )
        context["skip_count"] = skip_count

    if not glowny_autor:
        if pending_count == 0:
            messages.info(
                request,
                "Brak duplikatów do sprawdzenia. Wszystkie zostały już przetworzone.",
            )
        return render(request, "deduplikator_autorow/duplicate_authors.html", context)

    # Build context for the main author
    context["glowny_autor"] = glowny_autor

    # Try to get scientist for main author (for backward compatibility)
    if glowny_autor.pbn_uid:
        context["scientist"] = glowny_autor.pbn_uid

    # Build duplicate list from stored candidates
    duplikaty_z_publikacjami = []
    for candidate in candidates_for_author:
        pub_data = _build_context_from_candidate(candidate, glowny_autor)
        duplikaty_z_publikacjami.append(pub_data)

    context["duplikaty_z_publikacjami"] = duplikaty_z_publikacjami

    # Get main author's publications and disciplines
    context["glowny_autor_dyscypliny"] = (
        Autor_Dyscyplina.objects.filter(
            autor=glowny_autor, rok__gte=2022, rok__lte=2025
        )
        .select_related("dyscyplina_naukowa", "subdyscyplina_naukowa")
        .order_by("rok")
    )

    _add_dyscypliny_to_duplicates(duplikaty_z_publikacjami)

    glowny_autor_qs = Rekord.objects.prace_autora(glowny_autor)
    context["glowne_publikacje"] = glowny_autor_qs[:500]
    context["glowne_publikacje_count"] = glowny_autor_qs.count()
    context["glowne_publikacje_year_range"] = _calculate_year_range(glowny_autor_qs)

    return render(request, "deduplikator_autorow/duplicate_authors.html", context)


@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["GET", "POST"])
def scal_autorow_view(request):
    """
    Widok do scalania autorów automatycznie.

    Przyjmuje parametry:
    - main_scientist_id: ID głównego autora (Scientist)
    - duplicate_scientist_id: ID duplikatu autora (Scientist)
    - skip_pbn: Opcjonalnie, jeśli true nie wysyła publikacji do PBN
    - candidate_id: Opcjonalnie, ID DuplicateCandidate do oznaczenia jako scalony
    - auto_assign_discipline: Opcjonalnie, jeśli true przypisuje główną dyscyplinę
    - use_subdiscipline: Opcjonalnie, jeśli true używa subdyscypliny jako dyscypliny

    Zwraca wynik operacji w formacie JSON.
    """
    from django.utils import timezone

    if request.method == "GET":
        main_scientist_id = request.GET.get("main_scientist_id")
        duplicate_scientist_id = request.GET.get("duplicate_scientist_id")
        skip_pbn = request.GET.get("skip_pbn", "false").lower() == "true"
        candidate_id = request.GET.get("candidate_id")
        auto_assign_discipline = (
            request.GET.get("auto_assign_discipline", "false").lower() == "true"
        )
        use_subdiscipline = (
            request.GET.get("use_subdiscipline", "false").lower() == "true"
        )
    else:
        main_scientist_id = request.POST.get("main_scientist_id")
        duplicate_scientist_id = request.POST.get("duplicate_scientist_id")
        skip_pbn = request.POST.get("skip_pbn", "false").lower() == "true"
        candidate_id = request.POST.get("candidate_id")
        auto_assign_discipline = (
            request.POST.get("auto_assign_discipline", "false").lower() == "true"
        )
        use_subdiscipline = (
            request.POST.get("use_subdiscipline", "false").lower() == "true"
        )

    if not main_scientist_id or not duplicate_scientist_id:
        return JsonResponse(
            {
                "success": False,
                "error": "Brak wymaganych parametrów: main_scientist_id i duplicate_scientist_id",
            },
            status=400,
        )

    try:
        result = scal_autorow(
            main_scientist_id,
            duplicate_scientist_id,
            request.user,
            skip_pbn=skip_pbn,
            auto_assign_discipline=auto_assign_discipline,
            use_subdiscipline=use_subdiscipline,
        )

        # Mark candidate as merged if provided
        if candidate_id and result.get("success"):
            try:
                candidate = DuplicateCandidate.objects.get(pk=candidate_id)
                candidate.status = DuplicateCandidate.Status.MERGED
                candidate.reviewed_at = timezone.now()
                candidate.reviewed_by = request.user
                candidate.save()
            except DuplicateCandidate.DoesNotExist:
                pass  # Candidate may have been deleted, that's ok

        return JsonResponse({"success": result.get("success", False), "result": result})
    except NotImplementedError as e:
        return JsonResponse({"success": False, "error": str(e)}, status=501)
    except Exception as e:
        traceback.print_exc()
        rollbar.report_exc_info(sys.exc_info())
        return JsonResponse(
            {"success": False, "error": f"Błąd podczas scalania autorów: {str(e)}"},
            status=500,
        )


@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["POST"])
def mark_non_duplicate(request):
    """
    Widok do oznaczania autora jako nie-duplikatu.

    Przyjmuje parametry:
    - scientist_pk: Primary key Scientist do zapisania jako nie-duplikat

    Zapisuje w modelu NotADuplicate i przekierowuje do następnego autora.
    """
    scientist_pk = request.POST.get("scientist_pk")

    if not scientist_pk:
        messages.error(request, "Brak wymaganego parametru: scientist_pk")
        return redirect("deduplikator_autorow:duplicate_authors")

    try:
        # Sprawdź czy Scientist istnieje
        autor = Autor.objects.get(pk=scientist_pk)

        # Zapisz jako nie-duplikat (get_or_create zapobiega duplikatom)
        not_duplicate, created = NotADuplicate.objects.update_or_create(
            autor=autor, defaults=dict(created_by=request.user)
        )

        if created:
            messages.success(request, f"Autor {autor} oznaczony jako nie-duplikat.")
        else:
            messages.info(
                request, f"Autor {autor} był już oznaczony jako nie-duplikat."
            )

    except Autor.DoesNotExist:
        messages.error(request, "Nie znaleziono autora o podanym ID.")
    except Exception as e:
        messages.error(request, f"Błąd podczas oznaczania autora: {str(e)}")

    # Przekieruj do następnego autora z duplikatami
    return redirect("deduplikator_autorow:duplicate_authors")


@group_required(GR_WPROWADZANIE_DANYCH)
def reset_skipped_authors(request):
    """
    Widok do resetowania listy pominiętych autorów i rozpoczęcia od początku.
    """
    # Wyczyść sesję z pominiętymi autorami i historią nawigacji
    session_keys_to_clear = ["skipped_authors", "navigation_history"]
    cleared_any = False

    for key in session_keys_to_clear:
        if key in request.session:
            del request.session[key]
            cleared_any = True

    if cleared_any:
        request.session.modified = True
        messages.success(
            request,
            "Lista pominiętych autorów i historia nawigacji zostały wyczyszczone. Rozpoczynasz od początku.",
        )

    return redirect("deduplikator_autorow:duplicate_authors")


@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["POST"])
def ignore_author(request):
    """
    Mark a scientist as ignored in the deduplication process.

    Parameters:
    - scientist_id: ID of the Scientist to ignore
    - reason: Optional reason for ignoring (from POST)
    """
    scientist_id = request.POST.get("scientist_id")
    reason = request.POST.get("reason", "")

    if not scientist_id:
        messages.error(request, "Brak wymaganego parametru: scientist_id")
        return redirect("deduplikator_autorow:duplicate_authors")

    try:
        scientist = Scientist.objects.get(pk=scientist_id)

        # Check if already ignored
        if IgnoredAuthor.objects.filter(scientist=scientist).exists():
            messages.warning(
                request, f"Autor {scientist} jest już oznaczony jako ignorowany."
            )
        else:
            # Get the BPP author if available
            autor = None
            if hasattr(scientist, "rekord_w_bpp"):
                autor = scientist.rekord_w_bpp

            IgnoredAuthor.objects.create(
                scientist=scientist, autor=autor, reason=reason, created_by=request.user
            )
            messages.success(
                request, f"Autor {scientist} został oznaczony jako ignorowany."
            )

        return redirect("deduplikator_autorow:duplicate_authors")

    except Scientist.DoesNotExist:
        messages.error(request, f"Nie znaleziono Scientist o ID: {scientist_id}")
        return redirect("deduplikator_autorow:duplicate_authors")
    except Exception as e:
        messages.error(request, f"Błąd podczas ignorowania autora: {str(e)}")
        return redirect("deduplikator_autorow:duplicate_authors")


@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["POST"])
def reset_ignored_authors(request):
    """
    Remove all ignored author markings.
    """
    count = IgnoredAuthor.objects.count()
    IgnoredAuthor.objects.all().delete()
    messages.success(request, f"Zresetowano {count} ignorowanych autorów.")
    return redirect("deduplikator_autorow:duplicate_authors")


@group_required(GR_WPROWADZANIE_DANYCH)
def reset_not_duplicates(request):
    """
    Widok do resetowania (usuwania) wszystkich rekordów NotADuplicate.
    """
    if request.method == "POST":
        count = NotADuplicate.objects.count()
        NotADuplicate.objects.all().delete()
        messages.success(
            request,
            f"Zresetowano {count} autorów oznaczonych jako nie-duplikat.",
        )
    return redirect("deduplikator_autorow:duplicate_authors")


@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["POST"])
def delete_author(request):
    """
    Widok do usuwania autora (tylko jeśli nie ma publikacji).
    """
    author_id = request.POST.get("author_id")

    if not author_id:
        messages.error(request, "Brak wymaganego parametru: author_id")
        return redirect("deduplikator_autorow:duplicate_authors")

    try:
        # Sprawdź czy autor istnieje
        autor = Autor.objects.get(pk=author_id)

        # Sprawdź czy autor ma publikacje
        publikacje_count = Rekord.objects.prace_autora(autor).count()

        if publikacje_count > 0:
            messages.error(
                request,
                f"Nie można usunąć autora {autor} - ma {publikacje_count} publikacji.",
            )
        else:
            # Usuń autora
            autor_name = str(autor)
            autor.delete()
            messages.success(
                request, f"Usunięto autora {autor_name} (brak publikacji)."
            )

    except Autor.DoesNotExist:
        messages.error(request, "Nie znaleziono autora o podanym ID.")
    except Exception as e:
        messages.error(request, f"Błąd podczas usuwania autora: {str(e)}")

    return redirect("deduplikator_autorow:duplicate_authors")


@group_required(GR_WPROWADZANIE_DANYCH)
def download_duplicates_xlsx(request):
    """
    Widok do pobierania listy duplikatów w formacie XLSX.

    Generuje plik XLSX ze wszystkimi autorami z duplikatami,
    zawierający głównego autora, jego PBN UID, duplikat i jego PBN UID.
    """
    import datetime

    from django.http import HttpResponse

    try:
        # Generuj plik XLSX
        xlsx_content = export_duplicates_to_xlsx()

        # Stwórz odpowiedź HTTP z plikiem
        response = HttpResponse(
            xlsx_content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        # Nazwa pliku z datą
        filename = (
            f"duplikaty_autorow_{datetime.date.today().strftime('%Y-%m-%d')}.xlsx"
        )
        response["Content-Disposition"] = f'attachment; filename="{filename}"'

        return response

    except Exception as e:
        rollbar.report_exc_info(sys.exc_info())
        messages.error(request, f"Błąd podczas generowania pliku XLSX: {str(e)}")
        return redirect("deduplikator_autorow:duplicate_authors")


def get_latest_completed_scan():
    """Get the most recent completed scan run."""
    return (
        DuplicateScanRun.objects.filter(status=DuplicateScanRun.Status.COMPLETED)
        .order_by("-finished_at")
        .first()
    )


def get_running_scan():
    """Get the currently running scan, if any."""
    return DuplicateScanRun.objects.filter(
        status=DuplicateScanRun.Status.RUNNING
    ).first()


@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["POST"])
def start_scan_view(request):
    """
    Start a new duplicate scan task.
    """
    from .tasks import scan_for_duplicates

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
    from .tasks import cancel_scan

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


def _get_pending_candidates_for_main_autor(main_autor_id, scan_run):
    """Get pending duplicate candidates for a specific main author."""
    return (
        DuplicateCandidate.objects.filter(
            scan_run=scan_run,
            main_autor_id=main_autor_id,
            status=DuplicateCandidate.Status.PENDING,
        )
        .select_related("main_autor", "duplicate_autor")
        .order_by("-priority", "-confidence_score")
    )


def _get_next_candidate_group(scan_run, skip_count=0):
    """
    Get the next group of candidates (all for the same main author).
    Returns (main_autor, candidates_queryset, skip_count) or (None, None, 0) if no more pending.

    Args:
        scan_run: The scan run to get candidates from
        skip_count: Number of main authors to skip (offset)

    Returns:
        Tuple of (main_autor, candidates_queryset, current_skip_count)
    """
    # Get distinct main authors with pending candidates, ordered by priority then confidence
    # We need to find distinct main_autor_ids in priority/confidence order
    distinct_main_autor_ids = (
        DuplicateCandidate.objects.filter(
            scan_run=scan_run,
            status=DuplicateCandidate.Status.PENDING,
        )
        .order_by("-priority", "-confidence_score", "main_autor_id")
        .values_list("main_autor_id", flat=True)
        .distinct()
    )

    # Convert to list to enable indexing
    main_autor_ids = list(distinct_main_autor_ids)

    if not main_autor_ids:
        return None, None, 0

    # Ensure skip_count is within bounds
    if skip_count >= len(main_autor_ids):
        skip_count = 0  # Wrap around to beginning

    # Get the main author at the skip_count position
    main_autor_id = main_autor_ids[skip_count]

    try:
        main_autor = Autor.objects.get(pk=main_autor_id)
    except Autor.DoesNotExist:
        return None, None, 0

    # Get all pending candidates for this main author
    candidates = _get_pending_candidates_for_main_autor(main_autor_id, scan_run)

    return main_autor, candidates, skip_count


@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["POST"])
def mark_candidate_not_duplicate(request):
    """
    Mark a DuplicateCandidate as not a duplicate.
    """
    from django.utils import timezone

    candidate_id = request.POST.get("candidate_id")

    if not candidate_id:
        messages.error(request, "Brak wymaganego parametru: candidate_id")
        return redirect("deduplikator_autorow:duplicate_authors")

    try:
        candidate = DuplicateCandidate.objects.get(pk=candidate_id)
        candidate.status = DuplicateCandidate.Status.NOT_DUPLICATE
        candidate.reviewed_at = timezone.now()
        candidate.reviewed_by = request.user
        candidate.save()

        # Also mark the duplicate author in NotADuplicate (existing model)
        NotADuplicate.objects.update_or_create(
            autor=candidate.duplicate_autor, defaults={"created_by": request.user}
        )

        messages.success(
            request,
            f"Autor {candidate.duplicate_autor_name} oznaczony jako nie-duplikat.",
        )

    except DuplicateCandidate.DoesNotExist:
        messages.error(request, "Nie znaleziono kandydata o podanym ID.")
    except Exception as e:
        messages.error(request, f"Błąd podczas oznaczania kandydata: {str(e)}")

    return redirect("deduplikator_autorow:duplicate_authors")
