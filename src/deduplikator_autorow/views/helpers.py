"""Helper utilities used across deduplikator_autorow views.

Contains:
- ``group_required`` decorator (auth + group membership check)
- session navigation helpers (``_get_excluded_authors_from_session``,
  ``_handle_*``)
- duplicate-data builders (``_build_*``, ``_add_dyscypliny_to_duplicates``)
- scan/candidate query helpers (``get_latest_completed_scan``,
  ``get_running_scan``, ``_get_next_candidate_group``)

Public symbols re-exported via ``deduplikator_autorow.views`` for backward
compatibility.
"""

from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied

from bpp.models import Autor
from bpp.models.cache import Rekord
from pbn_api.models import Scientist

from ..models import DuplicateCandidate, DuplicateScanRun
from ..utils import (
    count_authors_with_lastname,
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
    Returns (main_autor, candidates_queryset, skip_count) or
    (None, None, 0) if no more pending.

    Args:
        scan_run: The scan run to get candidates from
        skip_count: Number of main authors to skip (offset)

    Returns:
        Tuple of (main_autor, candidates_queryset, current_skip_count)
    """
    # Get distinct main authors with pending candidates, ordered by
    # priority then confidence. We need to find distinct main_autor_ids
    # in priority/confidence order.
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
