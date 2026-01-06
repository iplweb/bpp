"""Widoki analizy możliwości zamiany dyscyplin."""

import logging

from celery.result import AsyncResult
from celery_singleton import DuplicateTaskError
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse

from bpp.models import Uczelnia

logger = logging.getLogger(__name__)


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


@login_required
def analyze_discipline_swap_opportunities(request):
    """
    Uruchamia zadanie analizy możliwości zamiany dyscyplin.

    Analizuje publikacje z lat 2022-2025 gdzie zamiana dyscypliny
    autora z głównej na subdyscyplinę (lub odwrotnie) zwiększa
    całkowitą punktację.
    """
    from ..models import StatusDisciplineSwapAnalysis
    from ..tasks import analyze_discipline_swap_task

    uczelnia = Uczelnia.objects.first()

    if not uczelnia:
        messages.error(request, "Nie znaleziono uczelni w systemie.")
        return redirect("ewaluacja_optymalizacja:index")

    # Sprawdź czy zadanie już działa
    status = StatusDisciplineSwapAnalysis.get_or_create()
    if status.w_trakcie and status.task_id:
        messages.info(
            request,
            "Zadanie analizy zamiany dyscyplin już działa. Przekierowuję do statusu.",
        )
        return redirect(
            "ewaluacja_optymalizacja:discipline-swap-status",
            task_id=status.task_id,
        )

    # Uruchom zadanie
    try:
        task = analyze_discipline_swap_task.delay(uczelnia.pk)
    except DuplicateTaskError:
        messages.error(
            request, "Zadanie analizy zamiany dyscyplin jest już uruchomione."
        )
        return redirect("ewaluacja_optymalizacja:index")

    logger.info(f"Started discipline swap analysis task: {task.id}")

    messages.info(
        request,
        "Rozpoczęto analizę możliwości zamiany dyscyplin. "
        "Zostaniesz przekierowany do strony postępu.",
    )

    return redirect("ewaluacja_optymalizacja:discipline-swap-status", task_id=task.id)


@login_required
def discipline_swap_status(request, task_id):
    """
    Wyświetla status zadania analizy zamiany dyscyplin.
    Obsługuje HTMX partial updates.
    """
    from ..models import StatusDisciplineSwapAnalysis

    task = AsyncResult(task_id)

    context = {
        "task_id": task_id,
    }

    # Pobierz informacje o zadaniu
    task_info = task.info if task.info and isinstance(task.info, dict) else {}
    current_stage = task_info.get("stage", "unknown")

    logger.debug(
        f"Checking discipline swap task {task_id}: stage={current_stage}, "
        f"task.info={task_info}"
    )

    # Jeśli zadanie się nie zakończyło
    if not task.ready():
        context["task_state"] = "PROGRESS"
        context["task_ready"] = False
        context["info"] = task_info

        # Format estimated time
        if task_info.get("eta_seconds"):
            context["info"]["estimated_time_formatted"] = _format_estimated_time(
                task_info["eta_seconds"]
            )

    # Sprawdź czy zadanie zakończyło się błędem
    elif task.failed():
        error_info = str(task.info)
        logger.error(f"Task {task_id} failed: {error_info}")

        # Wyczyść status
        status = StatusDisciplineSwapAnalysis.get_or_create()
        status.zakoncz(f"Błąd: {error_info[:200]}")

        context["error"] = error_info
        context["success"] = False
        context["task_ready"] = True

    # Zadanie zakończone pomyślnie
    elif task.successful():
        result = task.result
        logger.info(f"Task {task_id} successful: {result}")

        messages.success(
            request,
            f"Analiza zakończona! "
            f"Znaleziono {result.get('total_opportunities', 0)} możliwości zamiany, "
            f"w tym {result.get('sensible_opportunities', 0)} sensownych.",
        )

        # Dla HTMX requests używamy nagłówka HX-Redirect
        if request.headers.get("HX-Request"):
            response = HttpResponse(status=200)
            response["HX-Redirect"] = reverse(
                "ewaluacja_optymalizacja:discipline-swap-list"
            )
            return response

        return redirect("ewaluacja_optymalizacja:discipline-swap-list")

    # Dla HTMX request zwróć tylko partial
    if request.headers.get("HX-Request"):
        return render(
            request,
            "ewaluacja_optymalizacja/_discipline_swap_progress.html",
            context,
        )

    return render(
        request,
        "ewaluacja_optymalizacja/discipline_swap_status.html",
        context,
    )
