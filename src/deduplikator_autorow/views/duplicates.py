"""Main duplicate-browsing/resolution views.

Includes the primary list view (``duplicate_authors_view``), the
mark-as-not-duplicate endpoints, navigation reset, and the lastname
autocomplete used by the search bar.
"""

import sys
import traceback

import rollbar
from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Autor
from bpp.models.cache import Rekord
from pbn_downloader_app.freshness import is_pbn_people_data_fresh
from pbn_downloader_app.models import PbnDownloadTask

from ..models import (
    DuplicateCandidate,
    IgnoredScientist,
    LogScalania,
    NotADuplicate,
)
from ..utils.counters import get_latest_usable_scan
from .helpers import (
    MIN_PEWNOSC_DO_WYSWIETLENIA,
    _add_dyscypliny_to_duplicates,
    _build_context_from_candidate,
    _calculate_year_range,
    _get_next_candidate_group,
    get_running_scan,
    group_required,
)

TEMPLATE_DUPLICATE_AUTHORS = "deduplikator_autorow/duplicate_authors.html"


def _normalize_choice(value, allowed, default):
    """Zwróć ``value`` jeśli jest w ``allowed``, inaczej ``default``."""
    return value if value in allowed else default


def _parse_skip_count(request):
    """Wczytaj skip_count z GET jako int, z fallbackiem 0."""
    try:
        return int(request.GET.get("skip_count", 0))
    except (ValueError, TypeError):
        return 0


def _build_base_context(request, running_scan, completed_scan, mode):
    """Zbuduj wspólny kontekst używany we wszystkich scenariuszach widoku."""
    pbn_data_fresh, pbn_stale_message, pbn_last_download = is_pbn_people_data_fresh()
    recent_merges = (
        LogScalania.objects.filter(created_by=request.user)
        .select_related("main_autor", "dyscyplina_before", "dyscyplina_after")
        .order_by("-created_on")[:10]
    )
    return {
        "scientist": None,
        "glowny_autor": None,
        "latest_pbn_download": PbnDownloadTask.get_latest_task(),
        "duplikaty_z_publikacjami": [],
        "analiza": None,
        "has_skipped_authors": False,
        "has_previous_authors": False,
        "total_authors_with_duplicates": 0,
        "not_duplicate_count": NotADuplicate.objects.count(),
        "ignored_authors_count": IgnoredScientist.objects.count(),
        "search_lastname": "",
        "search_results_count": None,
        "recent_merges": recent_merges,
        # New scan-related context
        "running_scan": running_scan,
        "completed_scan": completed_scan,
        "no_scan_available": not completed_scan and not running_scan,
        "pending_candidates_count": 0,
        "pending_pbn_count": 0,
        "pending_general_count": 0,
        # Filter mode (pbn|general|both)
        "mode": mode,
        # Navigation
        "skip_count": 0,
        # PBN data freshness
        "pbn_data_fresh": pbn_data_fresh,
        "pbn_stale_message": pbn_stale_message,
        "pbn_last_download": pbn_last_download,
    }


def _add_pending_counts(context, completed_scan, confidence_band):
    """Policz PENDING-ujące kandydaty i wstaw liczniki do kontekstu."""
    base_pending_qs = DuplicateCandidate.objects.filter(
        scan_run=completed_scan,
        status=DuplicateCandidate.Status.PENDING,
    )
    pending_count = base_pending_qs.count()
    context["pending_candidates_count"] = pending_count
    context["total_authors_with_duplicates"] = pending_count
    context["pending_pbn_count"] = base_pending_qs.filter(scan_mode="pbn").count()
    context["pending_general_count"] = base_pending_qs.filter(
        scan_mode="general"
    ).count()
    context["confidence_band"] = confidence_band


def _resolve_by_search(request, completed_scan, mode, search_lastname, context):
    """Wybierz głównego autora i jego kandydatów na podstawie nazwiska.

    confidence_band celowo NIE filtruje wyboru głównego autora (filtr per-autor
    stosujemy później, na liście candidates_for_author).
    """
    candidates = (
        DuplicateCandidate.objects.filter(
            scan_run=completed_scan,
            status=DuplicateCandidate.Status.PENDING,
            main_autor__nazwisko__icontains=search_lastname,
        )
        .select_related("main_autor", "duplicate_autor")
        .order_by("-priority", "-confidence_score")
    )
    if mode != "both":
        candidates = candidates.filter(scan_mode=mode)

    context["search_results_count"] = candidates.values("main_autor").distinct().count()

    if not candidates.exists():
        return None, DuplicateCandidate.objects.none()

    search_author_ids = list(
        candidates.values_list("main_autor", flat=True)
        .distinct()
        .order_by("main_autor")
    )
    skip_count = _parse_skip_count(request)
    if skip_count >= len(search_author_ids):
        skip_count = 0
    glowny_autor = Autor.objects.get(pk=search_author_ids[skip_count])
    candidates_for_author = candidates.filter(main_autor=glowny_autor)
    context["skip_count"] = skip_count
    context["search_total_authors"] = len(search_author_ids)
    context["search_has_prev"] = skip_count > 0
    context["search_has_next"] = skip_count < len(search_author_ids) - 1
    return glowny_autor, candidates_for_author


def _resolve_by_navigation(request, completed_scan, mode, context):
    """Wybierz kolejnego głównego autora poprzez offset skip_count.

    confidence_band NIE jest tu przekazywane — chcemy iterować po WSZYSTKICH
    głównych autorach niezależnie od pewności ich kandydatów, filtr stosujemy
    później tylko na widocznym podzbiorze.
    """
    glowny_autor, candidates_for_author, skip_count = _get_next_candidate_group(
        completed_scan,
        skip_count=_parse_skip_count(request),
        mode=mode,
    )
    context["skip_count"] = skip_count
    return glowny_autor, candidates_for_author


def _apply_confidence_band(
    candidates_for_author, glowny_autor, confidence_band, threshold, context
):
    """Policz liczniki per-band i przefiltruj listę widocznych kandydatów."""
    if glowny_autor:
        total = candidates_for_author.count()
        high = candidates_for_author.filter(confidence_percent__gte=threshold).count()
        low = total - high
    else:
        total = high = low = 0
    if confidence_band == "high":
        candidates_for_author = candidates_for_author.filter(
            confidence_percent__gte=threshold
        )
    elif confidence_band == "low":
        candidates_for_author = candidates_for_author.filter(
            confidence_percent__lt=threshold
        )
    context["candidates_total_for_main"] = total
    context["candidates_high_for_main"] = high
    context["candidates_low_for_main"] = low
    return candidates_for_author


def _build_main_author_context(context, glowny_autor, candidates_for_author):
    """Uzupełnij kontekst danymi głównego autora i jego duplikatów."""
    from bpp.models import Autor_Dyscyplina

    context["glowny_autor"] = glowny_autor

    # Try to get scientist for main author (for backward compatibility)
    if glowny_autor.pbn_uid:
        context["scientist"] = glowny_autor.pbn_uid

    duplikaty_z_publikacjami = [
        _build_context_from_candidate(candidate, glowny_autor)
        for candidate in candidates_for_author
    ]
    context["duplikaty_z_publikacjami"] = duplikaty_z_publikacjami
    context["first_candidate"] = (
        candidates_for_author.first() if candidates_for_author else None
    )

    # "Scal wszystkie" jest aktywne tylko wtedy, gdy KAŻDY kandydat ma pewność
    # ≥ MIN_PEWNOSC_DO_WYSWIETLENIA. Przy słabych trafieniach przyciski
    # renderujemy w stanie wyszarzonym i klik pokazuje komunikat tłumaczący,
    # co zrobić dalej (lista nazwisk z niską pewnością).
    low_confidence_names = [
        f"{d['autor']} ({d['analiza']['pewnosc']}%)"
        for d in duplikaty_z_publikacjami
        if d["analiza"]["pewnosc"] < MIN_PEWNOSC_DO_WYSWIETLENIA
    ]
    context["allow_merge_all"] = (
        bool(duplikaty_z_publikacjami) and not low_confidence_names
    )
    context["low_confidence_names"] = low_confidence_names
    context["MIN_PEWNOSC_DO_WYSWIETLENIA"] = MIN_PEWNOSC_DO_WYSWIETLENIA

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


@group_required(GR_WPROWADZANIE_DANYCH)
def duplicate_authors_view(request):
    """
    Widok pokazujący główny rekord autora wraz z możliwymi duplikatami
    i ich publikacjami (do 500 na duplikat).

    Uses pre-computed duplicates from DuplicateCandidate table.
    """
    running_scan = get_running_scan()
    completed_scan = get_latest_usable_scan()

    # Filter mode: pbn|general|both (default both)
    mode = _normalize_choice(
        request.GET.get("mode", "both"), ("pbn", "general", "both"), "both"
    )
    # Filter confidence band: all|high|low (default all). high=>=50%, low=<50%.
    # Próg porównujemy do confidence_percent jako ułamka, bo display % jest
    # liczone z confidence_percent * 100 z klampem.
    confidence_band = _normalize_choice(
        request.GET.get("confidence", "all"), ("all", "high", "low"), "all"
    )
    confidence_threshold_frac = MIN_PEWNOSC_DO_WYSWIETLENIA / 100.0

    context = _build_base_context(request, running_scan, completed_scan, mode)

    # If no completed scan, show "run scan first" message
    if not completed_scan:
        if running_scan:
            messages.info(
                request,
                f"Skanowanie w toku: {running_scan.progress_percent}% "
                f"({running_scan.authors_scanned}/{running_scan.total_authors_to_scan} autorów)",
            )
        return render(request, TEMPLATE_DUPLICATE_AUTHORS, context)

    _add_pending_counts(context, completed_scan, confidence_band)

    # Handle search by lastname
    search_lastname = request.GET.get("search_lastname", "").strip()
    context["search_lastname"] = search_lastname

    if search_lastname:
        glowny_autor, candidates_for_author = _resolve_by_search(
            request, completed_scan, mode, search_lastname, context
        )
    else:
        glowny_autor, candidates_for_author = _resolve_by_navigation(
            request, completed_scan, mode, context
        )

    candidates_for_author = _apply_confidence_band(
        candidates_for_author,
        glowny_autor,
        confidence_band,
        confidence_threshold_frac,
        context,
    )

    if not glowny_autor:
        if context["pending_candidates_count"] == 0:
            messages.info(
                request,
                "Brak duplikatów do sprawdzenia. Wszystkie zostały już przetworzone.",
            )
        return render(request, TEMPLATE_DUPLICATE_AUTHORS, context)

    _build_main_author_context(context, glowny_autor, candidates_for_author)
    return render(request, TEMPLATE_DUPLICATE_AUTHORS, context)


@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["POST"])
def mark_non_duplicate(request):
    """
    Widok do oznaczania autora jako nie-duplikatu.

    Przyjmuje parametry:
    - scientist_pk: Primary key Scientist do zapisania jako nie-duplikat

    Zwraca JSON dla AJAX (X-Requested-With), w przeciwnym razie redirect.
    """
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    scientist_pk = request.POST.get("scientist_pk")

    def _respond(success, message, status=200, level="success"):
        if is_ajax:
            return JsonResponse({"success": success, "message": message}, status=status)
        if level == "info":
            messages.info(request, message)
        elif success:
            messages.success(request, message)
        else:
            messages.error(request, message)
        return redirect("deduplikator_autorow:duplicate_authors")

    if not scientist_pk:
        return _respond(False, "Brak wymaganego parametru: scientist_pk", status=400)

    try:
        autor = Autor.objects.get(pk=scientist_pk)

        not_duplicate, created = NotADuplicate.objects.update_or_create(
            autor=autor, defaults=dict(created_by=request.user)
        )

        if created:
            return _respond(True, f"Autor {autor} oznaczony jako nie-duplikat.")
        return _respond(
            True, f"Autor {autor} był już oznaczony jako nie-duplikat.", level="info"
        )

    except Autor.DoesNotExist:
        return _respond(False, "Nie znaleziono autora o podanym ID.", status=404)
    except Exception:
        traceback.print_exc()
        rollbar.report_exc_info(sys.exc_info())
        return _respond(
            False,
            "Wystąpił wewnętrzny błąd podczas oznaczania autora. Spróbuj ponownie później.",
            status=500,
        )


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
def reset_not_duplicates(request):
    """Widok do resetowania (usuwania) wszystkich rekordów NotADuplicate."""
    from .ignore import _trigger_rescan_after_reset

    if request.method == "POST":
        count = NotADuplicate.objects.count()
        NotADuplicate.objects.all().delete()
        _trigger_rescan_after_reset(
            request, f"Zresetowano {count} autorów oznaczonych jako nie-duplikat"
        )
    return redirect("deduplikator_autorow:duplicate_authors")


@group_required(GR_WPROWADZANIE_DANYCH)
def lastname_suggestions(request):
    """Autocomplete dla wyszukiwarki nazwisk w deduplikatorze.

    Zwraca top-10 unikalnych nazwisk autorów-głównych z PENDING-ujących
    DuplicateCandidate filtrowanych po prefiksie. Bez aktywnego skanu
    zwraca pustą listę. Wykorzystywane przez datalist na pasku górnym.
    """
    q = (request.GET.get("q") or "").strip()
    if not q or len(q) < 2:
        return JsonResponse({"results": []})

    completed_scan = get_latest_usable_scan()
    if not completed_scan:
        return JsonResponse({"results": []})

    nazwiska = (
        DuplicateCandidate.objects.filter(
            scan_run=completed_scan,
            status=DuplicateCandidate.Status.PENDING,
            main_autor__nazwisko__istartswith=q,
        )
        .values_list("main_autor__nazwisko", flat=True)
        .distinct()
        .order_by("main_autor__nazwisko")[:10]
    )
    return JsonResponse({"results": list(nazwiska)})


@group_required(GR_WPROWADZANIE_DANYCH)
@require_http_methods(["POST"])
def mark_candidate_not_duplicate(request):
    """
    Mark a DuplicateCandidate as not a duplicate.

    Returns JSON when called via AJAX (X-Requested-With: XMLHttpRequest),
    otherwise redirects.
    """
    from django.utils import timezone

    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    candidate_id = request.POST.get("candidate_id")

    def _respond(success, message, status=200):
        if is_ajax:
            return JsonResponse({"success": success, "message": message}, status=status)
        if success:
            messages.success(request, message)
        else:
            messages.error(request, message)
        return redirect("deduplikator_autorow:duplicate_authors")

    if not candidate_id:
        return _respond(False, "Brak wymaganego parametru: candidate_id", status=400)

    try:
        candidate = DuplicateCandidate.objects.get(pk=candidate_id)
        candidate.status = DuplicateCandidate.Status.NOT_DUPLICATE
        candidate.reviewed_at = timezone.now()
        candidate.reviewed_by = request.user
        candidate.save()

        NotADuplicate.objects.update_or_create(
            autor=candidate.duplicate_autor, defaults={"created_by": request.user}
        )

        return _respond(
            True,
            f"Autor {candidate.duplicate_autor_name} oznaczony jako nie-duplikat.",
        )

    except DuplicateCandidate.DoesNotExist:
        return _respond(False, "Nie znaleziono kandydata o podanym ID.", status=404)
    except Exception:
        traceback.print_exc()
        rollbar.report_exc_info(sys.exc_info())
        return _respond(
            False, "Wystąpił wewnętrzny błąd podczas oznaczania kandydata.", status=500
        )
