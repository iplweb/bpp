"""Widoki analizy możliwości odpinania."""

import logging

from celery.result import AsyncResult
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

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


def _handle_unpinning_task_in_progress(context, task_info, current_stage, current_step):
    """Handle unpinning task that is still in progress."""
    from ewaluacja_metryki.models import StatusGenerowania

    context["task_state"] = "PROGRESS"
    context["task_ready"] = False
    context["info"] = task_info
    context["info"]["stage"] = current_stage
    context["info"]["step"] = current_step

    # Check if metrics generation is running and add real progress
    status = StatusGenerowania.get_or_create()
    if status.w_trakcie and current_stage == "unknown":
        # Metrics are still running, update stage info
        context["info"]["stage"] = "metrics"
        context["info"]["step"] = "calculating"
        # Calculate real progress based on StatusGenerowania
        if status.liczba_do_przetworzenia > 0:
            metrics_progress = int(
                (status.liczba_przetworzonych / status.liczba_do_przetworzenia) * 50
            )
            context["info"]["progress"] = metrics_progress
            context["info"]["analyzed"] = status.liczba_przetworzonych
            context["info"]["total"] = status.liczba_do_przetworzenia
        else:
            context["info"]["progress"] = 0

    # Format estimated time for stage 2 (unpinning)
    if task_info.get("estimated_seconds_remaining"):
        seconds = task_info["estimated_seconds_remaining"]
        context["info"]["estimated_time_formatted"] = _format_estimated_time(seconds)


def _handle_unpinning_task_failed(request, task_id, error_info):
    """Handle unpinning task that failed."""
    from ..models import StatusUnpinningAnalyzy

    logger.error(f"Task {task_id} failed: {error_info}")

    # Wyczyść status w modelu singleton
    status = StatusUnpinningAnalyzy.get_or_create()
    status.zakoncz(f"Błąd: {str(error_info)[:200]}")

    return {
        "error": error_info,
        "success": False,
        "task_ready": True,
    }


def _handle_unpinning_task_success(request, task_id, result):
    """Handle unpinning task that completed successfully."""
    from ..models import StatusUnpinningAnalyzy

    logger.info(f"Task {task_id} successful: {result}")

    # Wyczyść status w modelu singleton - zadanie zakończone
    status = StatusUnpinningAnalyzy.get_or_create()
    status.zakoncz("Analiza zakończona pomyślnie")

    messages.success(
        request,
        f"Analiza zakończona pomyślnie! "
        f"Przeliczono {result.get('metrics_count', 0)} metryk. "
        f"Znaleziono {result.get('total_opportunities', 0)} możliwości odpinania, "
        f"w tym {result.get('sensible_opportunities', 0)} sensownych.",
    )

    # Dla HTMX requests używamy nagłówka HX-Redirect aby wykonać full-page redirect
    if request.headers.get("HX-Request"):
        from django.http import HttpResponse
        from django.urls import reverse

        response = HttpResponse(status=200)
        response["HX-Redirect"] = reverse("ewaluacja_optymalizacja:unpinning-list")
        return response

    # Dla zwykłych requestów normalny redirect
    return redirect("ewaluacja_optymalizacja:unpinning-list")


@login_required
def analyze_unpinning_opportunities(request):
    """
    Uruchamia zadanie analizy możliwości odpinania prac wieloautorskich.

    ZAWSZE najpierw przelicza metryki (usuwa stare i generuje nowe),
    a następnie automatycznie uruchamia analizę prac wieloautorskich.

    Używa Celery chain do sekwencyjnego wykonania: metryki -> unpinning.
    """
    from celery import chain

    from ewaluacja_metryki.models import MetrykaAutora, StatusGenerowania
    from ewaluacja_metryki.tasks import generuj_metryki_task_parallel
    from ewaluacja_metryki.utils import get_default_rodzaje_autora

    from ..models import StatusUnpinningAnalyzy
    from ..tasks import run_unpinning_after_metrics_wrapper

    # Pobierz pierwszą uczelnię (zakładamy, że jest tylko jedna)
    uczelnia = Uczelnia.objects.first()

    if not uczelnia:
        messages.error(request, "Nie znaleziono uczelni w systemie.")
        return redirect("ewaluacja_optymalizacja:index")

    # Sprawdź czy zadanie już działa (przez model singleton)
    status_unpinning = StatusUnpinningAnalyzy.get_or_create()
    if status_unpinning.w_trakcie and status_unpinning.task_id:
        messages.info(
            request,
            "Zadanie analizy możliwości odpinania już działa. "
            "Przekierowuję do statusu.",
        )
        return redirect(
            "ewaluacja_optymalizacja:unpinning-combined-status",
            task_id=status_unpinning.task_id,
        )

    # Sprawdź czy przeliczanie metryk już trwa
    status = StatusGenerowania.get_or_create()

    if status.w_trakcie:
        messages.info(
            request,
            "Przeliczanie metryk jest już w trakcie. Poczekaj na zakończenie.",
        )
        return redirect("ewaluacja_optymalizacja:index")

    # Usuń stare metryki
    metryki_count = MetrykaAutora.objects.count()
    if metryki_count > 0:
        logger.info(f"Deleting {metryki_count} old metrics before recalculation...")
        MetrykaAutora.objects.all().delete()
        logger.info("Deleted old metrics")

    # Stwórz Celery chain: metryki -> unpinning
    # Pierwszy task (metryki) zwraca wynik, który jest przekazywany do drugiego (unpinning wrapper)
    workflow = chain(
        generuj_metryki_task_parallel.s(
            rodzaje_autora=get_default_rodzaje_autora(),
            nadpisz=True,
            przelicz_liczbe_n=True,
        ),  # Przelicz metryki z jawnymi parametrami
        run_unpinning_after_metrics_wrapper.s(  # Potem uruchom unpinning
            uczelnia_id=uczelnia.pk, dyscyplina_id=None, min_slot_filled=0.8
        ),
    )

    # Uruchom chain
    result = workflow.apply_async()

    logger.info(
        f"Started metrics->unpinning chain. Chain ID: {result.id}, "
        f"Parent task (metrics): {result.parent.id if result.parent else 'None'}"
    )

    # Zapisz status w modelu singleton
    status_unpinning.rozpocznij(task_id=str(result.id))

    messages.info(
        request,
        "Rozpoczęto przeliczanie metryk i analizę możliwości odpinania. "
        "Zostaniesz przekierowany do strony postępu.",
    )

    # Przekieruj do strony statusu - result.id to ID ostatniego zadania w chain (unpinning)
    return redirect(
        "ewaluacja_optymalizacja:unpinning-combined-status", task_id=result.id
    )


@login_required
def unpinning_combined_status(request, task_id):
    """
    Wyświetla status łączonego zadania: przeliczanie metryk + analiza unpinning.
    Supports HTMX partial updates.
    """
    task = AsyncResult(task_id)

    context = {
        "task_id": task_id,
    }

    # Pobierz informacje o zadaniu
    task_info = task.info if task.info and isinstance(task.info, dict) else {}
    current_stage = task_info.get("stage", "unknown")
    current_step = task_info.get("step", "unknown")

    logger.info(
        f"Checking combined task {task_id}: stage={current_stage}, step={current_step}, "
        f"task.info={task_info}"
    )

    # Jeśli zadanie się nie zakończyło
    if not task.ready():
        _handle_unpinning_task_in_progress(
            context, task_info, current_stage, current_step
        )

    # Sprawdź czy zadanie zakończyło się błędem
    elif task.failed():
        error_info = str(task.info)
        context.update(_handle_unpinning_task_failed(request, task_id, error_info))

    # Zadanie zakończone pomyślnie
    elif task.successful():
        result = task.result
        response = _handle_unpinning_task_success(request, task_id, result)
        if response:
            return response

    # If HTMX request, return only the progress partial
    if request.headers.get("HX-Request"):
        return render(
            request,
            "ewaluacja_optymalizacja/_unpinning_combined_progress.html",
            context,
        )

    return render(
        request, "ewaluacja_optymalizacja/unpinning_combined_status.html", context
    )


@login_required
def unpinning_analysis_status(request, task_id):
    """
    Wyświetla status zadania analizy możliwości odpinania.
    Supports HTMX partial updates.
    """
    task = AsyncResult(task_id)

    context = {
        "task_id": task_id,
    }

    # Pobierz informacje o zadaniu
    task_info = task.info if task.info and isinstance(task.info, dict) else {}
    current_step = task_info.get("step", "unknown")

    logger.info(
        f"Checking unpinning analysis task {task_id}: current step={current_step}, "
        f"task.info={task_info}"
    )

    # Jeśli zadanie się nie zakończyło
    if not task.ready():
        context["task_state"] = "PROGRESS"
        context["task_ready"] = False
        context["info"] = task_info
        context["info"]["step"] = current_step

    # Sprawdź czy zadanie zakończyło się błędem
    elif task.failed():
        error_info = str(task.info)
        logger.error(f"Task {task_id} failed: {error_info}")
        context["error"] = error_info
        context["success"] = False
        context["task_ready"] = True

    # Zadanie zakończone pomyślnie
    elif task.successful():
        result = task.result
        logger.info(f"Task {task_id} successful: {result}")

        messages.success(
            request,
            f"Analiza zakończona pomyślnie! "
            f"Znaleziono {result.get('total_opportunities', 0)} możliwości odpinania, "
            f"w tym {result.get('sensible_opportunities', 0)} sensownych.",
        )

        # Dla HTMX requests używamy nagłówka HX-Redirect aby wykonać full-page redirect
        if request.headers.get("HX-Request"):
            from django.http import HttpResponse
            from django.urls import reverse

            response = HttpResponse(status=200)
            response["HX-Redirect"] = reverse("ewaluacja_optymalizacja:unpinning-list")
            return response

        # Dla zwykłych requestów normalny redirect
        return redirect("ewaluacja_optymalizacja:unpinning-list")

    # If HTMX request, return only the progress partial
    if request.headers.get("HX-Request"):
        return render(
            request,
            "ewaluacja_optymalizacja/_unpinning_analysis_progress.html",
            context,
        )

    return render(
        request, "ewaluacja_optymalizacja/unpinning_analysis_status.html", context
    )
