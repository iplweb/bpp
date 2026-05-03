"""Views responsible for browsing duplicate-author candidates and resolving them.

Includes:
- ``duplicate_authors_view`` — main listing/browsing page
- ``mark_non_duplicate`` / ``mark_candidate_not_duplicate`` — flag entries
  as not duplicates
- ``reset_skipped_authors`` / ``reset_not_duplicates`` — clear session/db state
"""

from django.contrib import messages
from django.shortcuts import redirect, render
from django.utils import timezone
from django.views.decorators.http import require_http_methods

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Autor
from bpp.models.cache import Rekord
from pbn_downloader_app.freshness import is_pbn_people_data_fresh
from pbn_downloader_app.models import PbnDownloadTask

from ..models import DuplicateCandidate, IgnoredAuthor, LogScalania, NotADuplicate
from .helpers import (
    _add_dyscypliny_to_duplicates,
    _build_context_from_candidate,
    _calculate_year_range,
    _get_next_candidate_group,
    get_latest_completed_scan,
    get_running_scan,
    group_required,
)


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

    # Check PBN people data freshness
    pbn_data_fresh, pbn_stale_message, pbn_last_download = is_pbn_people_data_fresh()

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
        # PBN data freshness
        "pbn_data_fresh": pbn_data_fresh,
        "pbn_stale_message": pbn_stale_message,
        "pbn_last_download": pbn_last_download,
    }

    # If no completed scan, show "run scan first" message
    if not completed_scan:
        if running_scan:
            messages.info(
                request,
                f"Skanowanie w toku: {running_scan.progress_percent}% "
                f"({running_scan.authors_scanned}/"
                f"{running_scan.total_authors_to_scan} autorów)",
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
            "Lista pominiętych autorów i historia nawigacji zostały "
            "wyczyszczone. Rozpoczynasz od początku.",
        )

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
def mark_candidate_not_duplicate(request):
    """
    Mark a DuplicateCandidate as not a duplicate.
    """
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
            autor=candidate.duplicate_autor,
            defaults={"created_by": request.user},
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
