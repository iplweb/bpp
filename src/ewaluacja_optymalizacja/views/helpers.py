"""Funkcje pomocnicze dla widoków ewaluacja_optymalizacja."""

import logging
from decimal import Decimal

from django.db.models import Q

logger = logging.getLogger(__name__)

# Klucze sesji dla śledzenia postępu denormalizacji
DENORM_INITIAL_COUNT_SESSION_KEY = "denorm_initial_count"
DENORM_START_TIME_SESSION_KEY = "denorm_start_time"


def _add_run_statistics(run, uczelnia):
    """Add statistics to an optimization run object."""
    from ewaluacja_liczba_n.models import LiczbaNDlaUczelni

    # Użyj _calculate_liczba_n_stats żeby dostać procent slotów poza N
    author_results = run.author_results.select_related("rodzaj_autora").all()
    stats = _calculate_liczba_n_stats(run, author_results)

    # Dodaj procent slotów poza N do obiektu run
    run.outside_n_slots_pct = stats["non_n_slots_pct"]

    # Dodaj statystyki przypięć dla dyscypliny
    run.pin_stats = _get_discipline_pin_stats(run.dyscyplina_naukowa)

    # Pobierz liczbę N dla dyscypliny i oblicz 3*N oraz procent wypełnienia slotów
    try:
        liczba_n_obj = LiczbaNDlaUczelni.objects.get(
            uczelnia=uczelnia, dyscyplina_naukowa=run.dyscyplina_naukowa
        )
        run.liczba_3n = liczba_n_obj.liczba_n_ostateczna
        if run.liczba_3n > 0:
            run.slots_fill_pct = (run.total_slots / run.liczba_3n) * 100
        else:
            run.slots_fill_pct = None
    except LiczbaNDlaUczelni.DoesNotExist:
        run.liczba_3n = None
        run.slots_fill_pct = None

    return run


def _calculate_summary_statistics(recent_runs):
    """Calculate summary statistics from a list of runs."""
    summary = {
        "total_points": Decimal("0"),
        "total_publications": 0,
        "total_slots": Decimal("0"),
        "total_3n": Decimal("0"),
        "total_low_mono_weighted": Decimal("0"),  # suma LOW-MONO % * liczba publikacji
        "total_outside_n_weighted": Decimal("0"),  # suma sloty poza N % * liczba slotów
        "total_slots_fill_weighted": Decimal("0"),  # suma Sloty % * liczba slotów
        "total_publications_for_low_mono": 0,  # suma publikacji (dla średniej ważonej)
        "total_slots_for_outside_n": Decimal("0"),  # suma slotów (dla średniej ważonej)
        "total_slots_for_fill_pct": Decimal(
            "0"
        ),  # suma slotów z danymi 3*N (dla średniej ważonej)
        "total_pinned": 0,
        "total_unpinned": 0,
    }

    for run in recent_runs:
        summary["total_points"] += run.total_points
        summary["total_publications"] += run.total_publications
        summary["total_slots"] += run.total_slots
        summary["total_pinned"] += run.pin_stats["pinned"]
        summary["total_unpinned"] += run.pin_stats["unpinned"]

        # Dodaj 3*N do sumy jeśli dostępne
        if run.liczba_3n is not None:
            summary["total_3n"] += run.liczba_3n

        # Dla średniej ważonej LOW-MONO % (ważona liczbą publikacji)
        if run.total_publications > 0:
            summary["total_low_mono_weighted"] += (
                run.low_mono_percentage * run.total_publications
            )
            summary["total_publications_for_low_mono"] += run.total_publications

        # Dla średniej ważonej slotów poza N % (ważona liczbą slotów)
        if run.total_slots > 0:
            summary["total_outside_n_weighted"] += (
                Decimal(str(run.outside_n_slots_pct)) * run.total_slots
            )
            summary["total_slots_for_outside_n"] += run.total_slots

        # Dla średniej ważonej Sloty % (ważona liczbą slotów)
        if run.total_slots > 0 and run.slots_fill_pct is not None:
            summary["total_slots_fill_weighted"] += (
                Decimal(str(run.slots_fill_pct)) * run.total_slots
            )
            summary["total_slots_for_fill_pct"] += run.total_slots

    # Oblicz średnie ważone
    if summary["total_publications_for_low_mono"] > 0:
        summary["avg_low_mono_pct"] = (
            summary["total_low_mono_weighted"]
            / summary["total_publications_for_low_mono"]
        )
    else:
        summary["avg_low_mono_pct"] = Decimal("0")

    if summary["total_slots_for_outside_n"] > 0:
        summary["avg_outside_n_pct"] = (
            summary["total_outside_n_weighted"] / summary["total_slots_for_outside_n"]
        )
    else:
        summary["avg_outside_n_pct"] = Decimal("0")

    if summary["total_slots_for_fill_pct"] > 0:
        summary["avg_slots_fill_pct"] = (
            summary["total_slots_fill_weighted"] / summary["total_slots_for_fill_pct"]
        )
    else:
        summary["avg_slots_fill_pct"] = Decimal("0")

    # Oblicz procenty przypięte/odpięte
    total_pins = summary["total_pinned"] + summary["total_unpinned"]
    if total_pins > 0:
        summary["pinned_pct"] = (summary["total_pinned"] / total_pins) * 100
        summary["unpinned_pct"] = (summary["total_unpinned"] / total_pins) * 100
    else:
        summary["pinned_pct"] = Decimal("0")
        summary["unpinned_pct"] = Decimal("0")

    return summary


def _check_for_problematic_slots():
    """Check if there are problematic slots < 0.1 for authors with disciplines."""
    from bpp.models import Autor_Dyscyplina, Cache_Punktacja_Autora_Query

    autorzy_z_dyscyplinami = set(
        Autor_Dyscyplina.objects.filter(rok__gte=2022, rok__lte=2025)
        .values_list("autor_id", flat=True)
        .distinct()
    )

    return Cache_Punktacja_Autora_Query.objects.filter(
        slot__lt=Decimal("0.1"),
        rekord__rok__gte=2022,
        rekord__rok__lte=2025,
        autor_id__in=autorzy_z_dyscyplinami,
    ).exists()


def _calculate_liczba_n_stats(run, author_results):
    """
    Calculate statistics about liczba N vs non-liczba N authors

    Returns dict with:
    - n_points, n_slots, n_pubs: totals for liczba N authors
    - non_n_points, non_n_slots, non_n_pubs: totals for non-liczba N authors
    - n_percentage, non_n_percentage: percentage splits
    - low_mono_percentage: percentage of LOW-MONO publications
    - non_n_and_low_mono_percentage: combined percentage
    """
    # Initialize counters
    n_points = Decimal("0")
    n_slots = Decimal("0")
    n_pubs = 0

    non_n_points = Decimal("0")
    non_n_slots = Decimal("0")
    non_n_pubs = 0

    # Aggregate by liczba N status
    for author_result in author_results:
        is_in_n = author_result.rodzaj_autora and author_result.rodzaj_autora.jest_w_n

        pub_count = author_result.publications.count()

        if is_in_n:
            n_points += author_result.total_points
            n_slots += author_result.total_slots
            n_pubs += pub_count
        else:
            non_n_points += author_result.total_points
            non_n_slots += author_result.total_slots
            non_n_pubs += pub_count

    # Calculate percentages
    total_points = n_points + non_n_points
    total_slots = n_slots + non_n_slots
    total_pubs = n_pubs + non_n_pubs

    n_points_pct = float(n_points / total_points * 100) if total_points > 0 else 0
    non_n_points_pct = (
        float(non_n_points / total_points * 100) if total_points > 0 else 0
    )

    n_slots_pct = float(n_slots / total_slots * 100) if total_slots > 0 else 0
    non_n_slots_pct = float(non_n_slots / total_slots * 100) if total_slots > 0 else 0

    low_mono_pct = float(run.low_mono_percentage)

    # Combined percentage: LOW-MONO + slots from authors outside liczba N
    # Note: This is an approximation since LOW-MONO is percentage of publications, not slots
    # But it gives a rough indicator of "problematic" content
    non_n_and_low_mono_pct = non_n_slots_pct + low_mono_pct

    return {
        "n_points": n_points,
        "n_slots": n_slots,
        "n_pubs": n_pubs,
        "n_points_pct": n_points_pct,
        "n_slots_pct": n_slots_pct,
        "non_n_points": non_n_points,
        "non_n_slots": non_n_slots,
        "non_n_pubs": non_n_pubs,
        "non_n_points_pct": non_n_points_pct,
        "non_n_slots_pct": non_n_slots_pct,
        "low_mono_pct": low_mono_pct,
        "non_n_and_low_mono_pct": non_n_and_low_mono_pct,
        "total_points": total_points,
        "total_slots": total_slots,
        "total_pubs": total_pubs,
    }


def _get_discipline_pin_stats(dyscyplina_naukowa):
    """
    Oblicza statystyki przypięć/odpięć dla danej dyscypliny w latach 2022-2025.

    Liczy tylko rekordy gdzie autor ma Autor_Dyscyplina w latach 2022-2025
    dla tej dyscypliny.

    Args:
        dyscyplina_naukowa: Obiekt Dyscyplina_Naukowa

    Returns:
        dict: {'pinned': int, 'unpinned': int, 'total': int,
               'pinned_pct': float, 'unpinned_pct': float}
    """
    from bpp.models import (
        Autor_Dyscyplina,
        Patent_Autor,
        Wydawnictwo_Ciagle_Autor,
        Wydawnictwo_Zwarte_Autor,
    )

    # Pobierz autorów którzy mają Autor_Dyscyplina w latach 2022-2025 dla tej dyscypliny
    autorzy_ids = set(
        Autor_Dyscyplina.objects.filter(
            rok__gte=2022,
            rok__lte=2025,
            dyscyplina_naukowa=dyscyplina_naukowa,
        )
        .values_list("autor_id", flat=True)
        .distinct()
    )

    if not autorzy_ids:
        return {
            "pinned": 0,
            "unpinned": 0,
            "total": 0,
            "pinned_pct": 0.0,
            "unpinned_pct": 0.0,
        }

    # Filtr bazowy dla wszystkich modeli
    base_filter = Q(
        rekord__rok__gte=2022,
        rekord__rok__lte=2025,
        dyscyplina_naukowa=dyscyplina_naukowa,
        autor_id__in=autorzy_ids,
    )

    # Zlicz przypięte i odpięte dla każdego modelu
    pinned_count = 0
    unpinned_count = 0

    for model in [Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor, Patent_Autor]:
        pinned_count += model.objects.filter(base_filter, przypieta=True).count()
        unpinned_count += model.objects.filter(base_filter, przypieta=False).count()

    total = pinned_count + unpinned_count

    if total == 0:
        return {
            "pinned": 0,
            "unpinned": 0,
            "total": 0,
            "pinned_pct": 0.0,
            "unpinned_pct": 0.0,
        }

    pinned_pct = (pinned_count / total) * 100
    unpinned_pct = (unpinned_count / total) * 100

    return {
        "pinned": pinned_count,
        "unpinned": unpinned_count,
        "total": total,
        "pinned_pct": pinned_pct,
        "unpinned_pct": unpinned_pct,
    }


def _format_estimated_time(seconds):
    """Format estimated time in seconds to human-readable string."""
    if seconds >= 3600:
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        return f"{hours} godz. {minutes} min"
    elif seconds >= 60:
        minutes = int(seconds // 60)
        return f"{minutes} min"
    else:
        return "< 1 min"


def _get_dyscyplina_filter(request):
    """Extract and validate dyscyplina ID from request."""
    dyscyplina_id = request.GET.get("dyscyplina")
    if not dyscyplina_id:
        return None

    try:
        return int(dyscyplina_id)
    except (ValueError, TypeError):
        return None


def _cache_rekord_objects(opportunities_qs):
    """Preload Rekord objects to avoid N+1 queries."""
    from bpp.models import Rekord

    all_opportunities = list(opportunities_qs)
    rekord_ids = [opp.rekord_id for opp in all_opportunities]
    rekordy = {r.pk: r for r in Rekord.objects.filter(pk__in=rekord_ids)}

    # Attach rekord objects to opportunities
    for opp in all_opportunities:
        opp._cached_rekord = rekordy.get(opp.rekord_id)

    return all_opportunities


def _get_punkty_kbn(opportunity):
    """Safely get punkty_kbn from opportunity's rekord."""
    try:
        return opportunity.rekord.original.punkty_kbn or Decimal("0")
    except (AttributeError, TypeError):
        return Decimal("0")


def _filter_by_punktacja(opportunities, punktacja_zrodla):
    """Filter opportunities by punktacja_zrodla range."""
    if not punktacja_zrodla:
        return opportunities

    punktacja_ranges = {
        "0-100": lambda p: p < Decimal("100"),
        "100-140": lambda p: Decimal("100") <= p < Decimal("140"),
        "140-200": lambda p: Decimal("140") <= p < Decimal("200"),
        "200+": lambda p: p >= Decimal("200"),
    }

    filter_func = punktacja_ranges.get(punktacja_zrodla)
    if not filter_func:
        return opportunities

    return [opp for opp in opportunities if filter_func(_get_punkty_kbn(opp))]


def _create_sort_key_function(sort_by):
    """Create a sort key function based on sort_by parameter."""
    # Define sort key extractors
    sort_keys = {
        "tytul": lambda opp: opp.rekord_tytul or "",
        "punktacja": _get_punkty_kbn,
        "dyscyplina": lambda opp: (
            opp.dyscyplina_naukowa.nazwa if opp.dyscyplina_naukowa else ""
        ),
        "autor_a": lambda opp: (
            opp.autor_could_benefit.nazwisko if opp.autor_could_benefit else ""
        ),
        "slots_missing": lambda opp: opp.slots_missing or Decimal("0"),
        "slot_in_work": lambda opp: opp.slot_in_work or Decimal("0"),
        "punkty_a": lambda opp: opp.punkty_roznica_a or Decimal("0"),
        "sloty_a": lambda opp: opp.sloty_roznica_a or Decimal("0"),
        "punkty_b": lambda opp: opp.punkty_roznica_b or Decimal("0"),
        "sloty_b": lambda opp: opp.sloty_roznica_b or Decimal("0"),
        "autor_b": lambda opp: (
            opp.autor_currently_using.nazwisko if opp.autor_currently_using else ""
        ),
        "makes_sense": lambda opp: opp.makes_sense,
    }

    # Return the requested sort key function, defaulting to punkty_b
    return sort_keys.get(sort_by, sort_keys["punkty_b"])


def _update_session_if_needed(session, dirty_count, initial_count):
    """
    Update session if dirty_count increased above initial_count.

    Returns tuple (new_initial_count, new_start_time) if updated,
    or (initial_count, start_time) if not updated.
    """
    import time

    start_time = session.get(DENORM_START_TIME_SESSION_KEY)

    # Jeśli liczba rekordów wzrosła ponad początkową wartość, zaktualizuj sesję
    if dirty_count > 0 and initial_count and dirty_count > initial_count:
        # Zaktualizuj initial_count do nowej wyższej wartości
        session[DENORM_INITIAL_COUNT_SESSION_KEY] = dirty_count
        initial_count = dirty_count
        # Zresetuj czas rozpoczęcia
        session[DENORM_START_TIME_SESSION_KEY] = time.time()
        start_time = time.time()

    return initial_count, start_time


def _calculate_time_estimates(dirty_count, initial_count, start_time):
    """
    Calculate estimated time remaining and records per second.

    Returns tuple (estimated_time_remaining, records_per_second).
    Both values can be None if not enough data to calculate.
    """
    import time

    estimated_time_remaining = None
    records_per_second = None

    if dirty_count > 0 and initial_count and start_time:
        # Oblicz szacowany czas pozostały
        elapsed_time = time.time() - start_time
        records_processed = initial_count - dirty_count

        if elapsed_time > 5 and records_processed > 0:
            # Oblicz tempo przetwarzania (rekordów na sekundę)
            records_per_second = records_processed / elapsed_time
            # Oblicz szacowany czas pozostały (w sekundach)
            estimated_time_remaining = dirty_count / records_per_second

    return estimated_time_remaining, records_per_second


def _format_time_remaining(estimated_time_remaining):
    """
    Format estimated time remaining in seconds to human-readable Polish string.

    Returns formatted string or None if estimated_time_remaining is None.
    """
    if estimated_time_remaining is None:
        return None

    seconds = int(estimated_time_remaining)
    if seconds < 60:
        return f"{seconds} sek."
    elif seconds < 3600:
        minutes = seconds // 60
        secs = seconds % 60
        return f"{minutes} min {secs} sek."
    else:
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        return f"{hours} godz. {minutes} min"


def _calculate_progress_percentages(dirty_count, initial_count):
    """
    Calculate remaining and completed percentages.

    Returns tuple (remaining_pct, completed_pct).
    """
    if initial_count and initial_count > 0:
        remaining_pct = (dirty_count / initial_count) * 100
        completed_pct = 100 - remaining_pct
    else:
        remaining_pct = 0
        completed_pct = 0

    return remaining_pct, completed_pct


def _check_unpinning_task_status(status_unpinning):
    """
    Check if unpinning analysis task is still running.

    Returns True if task is running, False otherwise.
    If task finished, updates status_unpinning to mark completion.
    """
    from celery.result import AsyncResult

    if status_unpinning.w_trakcie and status_unpinning.task_id:
        task = AsyncResult(status_unpinning.task_id)
        if not task.ready():
            return True
        else:
            # Task finished, clean up database status
            status_unpinning.zakoncz("Zadanie zakończone")
            return False
    return False
