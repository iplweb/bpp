"""Widok główny modułu ewaluacja_optymalizacja."""

import logging
import time

from celery.result import AsyncResult
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render

from bpp.models import Uczelnia

from ..models import (
    OptimizationRun,
    StatusOptymalizacjiBulk,
    StatusOptymalizacjiZOdpinaniem,
    StatusUnpinningAnalyzy,
)
from .helpers import (
    DENORM_INITIAL_COUNT_SESSION_KEY,
    DENORM_START_TIME_SESSION_KEY,
    _add_run_statistics,
    _calculate_summary_statistics,
    _check_for_problematic_slots,
)

logger = logging.getLogger(__name__)


@login_required
def index(request):
    """
    Główny widok aplikacji ewaluacja_optymalizacja - lista wszystkich kalkulacji
    """

    from denorm.models import DirtyInstance

    from ewaluacja_liczba_n.models import LiczbaNDlaUczelni

    # Sprawdź czy są rekordy do przeliczenia
    dirty_count = DirtyInstance.objects.count()

    # Zapisz początkową liczbę rekordów i czas rozpoczęcia w sesji
    # (dla paska postępu w denorm_progress)
    if dirty_count > 0:
        request.session[DENORM_INITIAL_COUNT_SESSION_KEY] = dirty_count
        request.session[DENORM_START_TIME_SESSION_KEY] = time.time()
    else:
        # Wyczyść sesję jeśli nie ma rekordów do przeliczenia
        request.session.pop(DENORM_INITIAL_COUNT_SESSION_KEY, None)
        request.session.pop(DENORM_START_TIME_SESSION_KEY, None)

    runs = OptimizationRun.objects.select_related(
        "dyscyplina_naukowa", "uczelnia"
    ).all()

    # Pobierz uczelnię dla dalszych obliczeń
    uczelnia = Uczelnia.objects.first()

    # Dla każdego run oblicz procent slotów poza N oraz statystyki przypięć
    runs_with_stats = [_add_run_statistics(run, uczelnia) for run in runs]

    # Sprawdź czy są dane liczby N
    liczba_n_count = 0
    liczba_n_raportowane = 0

    if uczelnia:
        liczba_n_count = LiczbaNDlaUczelni.objects.filter(uczelnia=uczelnia).count()
        liczba_n_raportowane = LiczbaNDlaUczelni.objects.filter(
            uczelnia=uczelnia, liczba_n__gte=12
        ).count()

    # Oblicz agregacje dla ostatnich 10 wierszy (dla podsumowania w tabeli)
    recent_runs = runs_with_stats[:10]
    summary = _calculate_summary_statistics(recent_runs)

    # Sprawdź czy są problematyczne sloty < 0.1 dla przycisku weryfikacji
    has_problematic_slots = _check_for_problematic_slots()

    # Sprawdź czy działa optymalizacja z odpinaniem
    status_odpinania = StatusOptymalizacjiZOdpinaniem.get_or_create()
    status_bulk = StatusOptymalizacjiBulk.get_or_create()
    status_unpinning = StatusUnpinningAnalyzy.get_or_create()

    # Sprawdź czy trwa analiza "Optymalizuj przed" - używa modelu singleton zamiast sesji
    unpinning_analysis_running = False
    unpinning_task_id = None
    if status_unpinning.w_trakcie and status_unpinning.task_id:
        task = AsyncResult(status_unpinning.task_id)
        if not task.ready():
            unpinning_analysis_running = True
            unpinning_task_id = status_unpinning.task_id
        else:
            # Task finished, clean up database status
            status_unpinning.zakoncz("Zadanie zakończone")

    context = {
        "optimization_runs": runs_with_stats,
        "liczba_n_count": liczba_n_count,
        "liczba_n_raportowane": liczba_n_raportowane,
        "summary": summary,
        "dirty_count": dirty_count,
        "has_problematic_slots": has_problematic_slots,
        "status_odpinania": status_odpinania,
        "status_bulk": status_bulk,
        "status_unpinning": status_unpinning,
        "unpinning_analysis_running": unpinning_analysis_running,
        "unpinning_task_id": unpinning_task_id,
    }

    return render(request, "ewaluacja_optymalizacja/index.html", context)


@login_required
def denorm_progress(request):
    """
    Endpoint HTMX zwracający progress bar dla denormalizacji.
    Śledzi liczbę DirtyInstance i pokazuje postęp przeliczania.

    Używa sesji do odczytu początkowej liczby rekordów i czasu rozpoczęcia
    (ustawianych w widoku index przy ładowaniu strony głównej).
    """
    from denorm.models import DirtyInstance

    from .helpers import (
        _calculate_progress_percentages,
        _calculate_time_estimates,
        _check_unpinning_task_status,
        _format_time_remaining,
        _update_session_if_needed,
    )

    dirty_count = DirtyInstance.objects.count()

    # Pobierz dane z sesji (ustawiane w widoku index)
    initial_count = request.session.get(DENORM_INITIAL_COUNT_SESSION_KEY)

    # Zaktualizuj sesję jeśli potrzeba
    initial_count, start_time = _update_session_if_needed(
        request.session, dirty_count, initial_count
    )

    # Oblicz szacowany czas i tempo przetwarzania
    estimated_time_remaining, records_per_second = _calculate_time_estimates(
        dirty_count, initial_count, start_time
    )

    # Jeśli przeliczanie zakończone, wyczyść sesję
    if dirty_count == 0:
        request.session.pop(DENORM_INITIAL_COUNT_SESSION_KEY, None)
        request.session.pop(DENORM_START_TIME_SESSION_KEY, None)

    # Oblicz procenty postępu
    remaining_pct, completed_pct = _calculate_progress_percentages(
        dirty_count, initial_count
    )

    # Pokaż komunikat o zakończeniu jeśli było initial_count > 0 a teraz dirty_count == 0
    show_completed = (
        dirty_count == 0 and initial_count is not None and initial_count > 0
    )

    # Formatuj szacowany czas pozostały
    estimated_time_formatted = _format_time_remaining(estimated_time_remaining)

    # Sprawdź czy trwa analiza "Optymalizuj przed"
    status_unpinning = StatusUnpinningAnalyzy.get_or_create()
    unpinning_analysis_running = _check_unpinning_task_status(status_unpinning)

    context = {
        "dirty_count": dirty_count,
        "initial_count": initial_count,
        "remaining_pct": remaining_pct,
        "completed_pct": completed_pct,
        "show_completed": show_completed,
        "estimated_time_formatted": estimated_time_formatted,
        "records_per_second": int(records_per_second) if records_per_second else None,
        "unpinning_analysis_running": unpinning_analysis_running,
    }

    return render(request, "ewaluacja_optymalizacja/_denorm_progress.html", context)


@login_required
def trigger_denorm_flush(request):
    """
    Endpoint do ręcznego wyzwolenia flush_via_queue gdy denorm się zawiesi.
    Wywoływany automatycznie przez JavaScript gdy dirty_count nie zmienia się przez 15 sekund.
    Zwraca JSON z informacją o sukcesie.
    """
    from denorm.tasks import flush_via_queue

    if request.method == "POST":
        flush_via_queue.delay()
        return JsonResponse({"status": "ok", "message": "Flush triggered"})

    return JsonResponse({"status": "error", "message": "POST required"}, status=405)
