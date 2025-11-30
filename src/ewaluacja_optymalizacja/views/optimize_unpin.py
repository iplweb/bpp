"""Widoki optymalizacji z odpinaniem niewykazanych slotów."""

import logging

from celery.result import AsyncResult
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from bpp.models import Uczelnia

from ..models import (
    OptimizationAuthorResult,
    OptimizationPublication,
    OptimizationRun,
    StatusOptymalizacjiZOdpinaniem,
)
from .helpers import _format_time_remaining

logger = logging.getLogger(__name__)


def _verify_optimization_data_complete(raportowane_dyscypliny, uczelnia):
    """Verify that all optimization data is fully saved to database."""
    for liczba_n_obj in raportowane_dyscypliny:
        opt_run = (
            OptimizationRun.objects.filter(
                uczelnia=uczelnia,
                dyscyplina_naukowa=liczba_n_obj.dyscyplina_naukowa,
                status="completed",
            )
            .order_by("-started_at")
            .first()
        )

        if opt_run:
            has_authors = OptimizationAuthorResult.objects.filter(
                optimization_run=opt_run
            ).exists()
            has_publications = OptimizationPublication.objects.filter(
                author_result__optimization_run=opt_run
            ).exists()

            if not (has_authors and has_publications):
                logger.info(
                    f"Data not fully saved for {liczba_n_obj.dyscyplina_naukowa.nazwa}: "
                    f"authors={has_authors}, publications={has_publications}"
                )
                return False
        else:
            logger.warning(
                f"No optimization run found for {liczba_n_obj.dyscyplina_naukowa.nazwa}"
            )
            return False

    return True


def _determine_unpin_task_context(
    task,
    all_data_complete,
    completed_count,
    discipline_count,
    running_count,
    percent_complete,
):
    """Determine the context based on task status and data completion."""
    context_update = {}

    if task.ready():
        if task.failed():
            error_info = str(task.info)
            logger.error(f"Task {task.id} failed: {error_info}")
            context_update.update(
                {
                    "error": error_info,
                    "success": False,
                    "task_ready": True,
                    "task_state": "FAILURE",
                }
            )
        elif task.successful():
            # Task zakończony pomyślnie - pokaż sukces od razu
            # (bez czekania na all_data_complete)
            result = task.result
            logger.info(f"Task {task.id} successful")
            context_update.update(
                {
                    "result": result,
                    "success": True,
                    "task_ready": True,
                    "task_state": "SUCCESS",
                }
            )
    else:
        context_update["task_ready"] = False
        context_update["task_state"] = "PROGRESS"

        if completed_count >= discipline_count and discipline_count > 0:
            context_update["info"] = {
                "step": "finalizing",
                "progress": 99,
                "message": "Finalizowanie zadania...",
                "completed_optimizations": completed_count,
                "total_optimizations": discipline_count,
            }
        else:
            progress = (
                min(65 + int((completed_count / discipline_count) * 30), 95)
                if discipline_count > 0
                else 65
            )
            context_update["info"] = {
                "step": "optimization",
                "progress": progress,
                "message": (
                    f"Przeliczono {completed_count} z {discipline_count} "
                    f"dyscyplin ({percent_complete}%)"
                ),
                "running_optimizations": running_count,
                "completed_optimizations": completed_count,
                "total_optimizations": discipline_count,
            }

    return context_update


@login_required
def optimize_with_unpinning(request):
    """
    Uruchamia zadanie Celery do optymalizacji z odpinaniem niewykazanych slotów.
    """
    from denorm.models import DirtyInstance

    from ewaluacja_liczba_n.models import LiczbaNDlaUczelni

    from ..tasks import optimize_and_unpin_task

    # Sprawdź czy zadanie już działa (przez model singleton)
    status = StatusOptymalizacjiZOdpinaniem.get_or_create()
    if status.w_trakcie and status.task_id:
        messages.info(
            request,
            "Zadanie optymalizacji z odpinaniem już działa. Przekierowuję do statusu.",
        )
        return redirect(
            "ewaluacja_optymalizacja:optimize-unpin-status", task_id=status.task_id
        )

    # Sprawdź czy są rekordy do przeliczenia
    dirty_count = DirtyInstance.objects.count()
    if dirty_count > 0:
        messages.warning(
            request,
            f"Przed optymalizacją z odpinaniem poczekaj na przeliczenie punktów. "
            f"Obecnie jest {dirty_count} rekordów do przeliczenia.",
        )
        return redirect("ewaluacja_optymalizacja:index")

    # Pobierz pierwszą uczelnię (zakładamy, że jest tylko jedna)
    uczelnia = Uczelnia.objects.first()

    if not uczelnia:
        messages.error(request, "Nie znaleziono uczelni w systemie.")
        return redirect("ewaluacja_optymalizacja:index")

    # Sprawdź czy wszystkie dyscypliny raportowane są przeliczone
    liczba_n_raportowane = LiczbaNDlaUczelni.objects.filter(
        uczelnia=uczelnia, liczba_n__gte=12
    )

    if liczba_n_raportowane.count() == 0:
        messages.error(
            request,
            "Brak dyscyplin raportowanych (liczba N >= 12). "
            "Najpierw uruchom optymalizację dla dyscyplin.",
        )
        return redirect("ewaluacja_optymalizacja:index")

    # Sprawdź czy wszystkie dyscypliny raportowane mają wyniki optymalizacji
    for liczba_n_obj in liczba_n_raportowane:
        if not OptimizationRun.objects.filter(
            dyscyplina_naukowa=liczba_n_obj.dyscyplina_naukowa,
            uczelnia=uczelnia,
            status="completed",
        ).exists():
            messages.error(
                request,
                f"Dyscyplina {liczba_n_obj.dyscyplina_naukowa.nazwa} nie ma "
                "wykonanej optymalizacji. Najpierw uruchom 'Policz całą ewaluację'.",
            )
            return redirect("ewaluacja_optymalizacja:index")

    logger.info(f"Starting optimization with unpinning for {uczelnia}")

    # Uruchom zadanie Celery
    from celery_singleton import DuplicateTaskError

    try:
        task = optimize_and_unpin_task.delay(uczelnia.pk)
        # Zapisz status w modelu singleton
        status.rozpocznij(task_id=str(task.id))
    except DuplicateTaskError:
        # Fallback - celery_singleton złapał duplikat, ale model może mieć task_id
        if status.task_id:
            messages.info(
                request,
                "Zadanie optymalizacji z odpinaniem już działa. Przekierowuję do statusu.",
            )
            return redirect(
                "ewaluacja_optymalizacja:optimize-unpin-status", task_id=status.task_id
            )
        messages.error(
            request,
            "Zadanie optymalizacji z odpinaniem jest już uruchomione. "
            "Nie można ustalić ID zadania.",
        )
        return redirect("ewaluacja_optymalizacja:index")

    # Przekieruj do strony statusu
    return redirect("ewaluacja_optymalizacja:optimize-unpin-status", task_id=task.id)


def _handle_validation_or_snapshot_phase(
    request, task_id, current_step, task_info, context
):
    """Handle validation or snapshot phase rendering."""
    context["task_state"] = "PROGRESS"
    context["task_ready"] = False
    context["info"] = {
        "step": current_step,
        "progress": task_info.get("progress", 0),
        "message": task_info.get("message", ""),
    }

    logger.info(f"Task {task_id} in {current_step} phase")

    template = (
        "ewaluacja_optymalizacja/_optimize_unpin_progress.html"
        if request.headers.get("HX-Request")
        else "ewaluacja_optymalizacja/optimize_unpin_status.html"
    )
    return render(request, template, context)


def _handle_unpinning_phase(request, task_id, task_info, context):
    """Handle unpinning phase rendering."""
    # Format ETA if available
    eta_seconds = task_info.get("eta_seconds")
    eta_formatted = _format_time_remaining(eta_seconds) if eta_seconds else None

    context["task_state"] = "PROGRESS"
    context["task_ready"] = False
    context["info"] = {
        "step": "unpinning",
        "progress": task_info.get("progress", 20),
        "message": task_info.get("message", "Odpinanie slotów..."),
        "unpinning_phase": task_info.get("unpinning_phase", ""),
        "current_batch": task_info.get("current_batch", 0),
        "total_batches": task_info.get("total_batches", 0),
        "unpinned_so_far": task_info.get("unpinned_so_far", 0),
        "total_to_unpin": task_info.get("total_to_unpin", 0),
        "batches_processed_all": task_info.get("batches_processed_all", 0),
        "total_batches_all": task_info.get("total_batches_all", 0),
        "eta_formatted": eta_formatted,
    }

    logger.info(
        f"Task {task_id} in unpinning phase: "
        f"porcja {task_info.get('current_batch', 0)}/{task_info.get('total_batches', 0)}"
    )

    template = (
        "ewaluacja_optymalizacja/_optimize_unpin_progress.html"
        if request.headers.get("HX-Request")
        else "ewaluacja_optymalizacja/optimize_unpin_status.html"
    )
    return render(request, template, context)


def _handle_denorm_phase(request, task_id, task_info, context):
    """Handle denormalization phase rendering."""
    from denorm.models import DirtyInstance

    dirty_count = task_info.get("dirty_count", DirtyInstance.objects.count())
    context["task_state"] = "PROGRESS"
    context["task_ready"] = False
    context["info"] = {
        "step": "denorm",
        "progress": task_info.get("progress", 50),
        "dirty_count": dirty_count,
        "message": f"Przeliczanie punktacji - pozostało {dirty_count} obiektów",
        "unpinned_ciagle": task_info.get("unpinned_ciagle", 0),
        "unpinned_zwarte": task_info.get("unpinned_zwarte", 0),
    }

    logger.info(
        f"Task {task_id} in denorm phase: {dirty_count} dirty objects remaining"
    )

    template = (
        "ewaluacja_optymalizacja/_optimize_unpin_progress.html"
        if request.headers.get("HX-Request")
        else "ewaluacja_optymalizacja/optimize_unpin_status.html"
    )
    return render(request, template, context)


def _handle_task_completion(request, context):
    """Handle successful task completion with redirect."""
    status = StatusOptymalizacjiZOdpinaniem.get_or_create()
    status.zakoncz("Optymalizacja zakończona pomyślnie")

    result = context.get("result", {})
    unpinned_total = result.get("unpinned_total", 0)

    messages.success(
        request,
        f"Optymalizacja z odpinaniem zakończona pomyślnie! Odpiętych publikacji: {unpinned_total}",
    )

    if request.headers.get("HX-Request"):
        from django.http import HttpResponse
        from django.urls import reverse

        response = HttpResponse(status=200)
        response["HX-Redirect"] = reverse("ewaluacja_optymalizacja:index")
        return response

    return redirect("ewaluacja_optymalizacja:index")


@login_required
def optimize_unpin_status(request, task_id):
    """
    Wyświetla status zadania optymalizacji z odpinaniem.
    - Dla fazy "denorm": pokazuje postęp denormalizacji (używa task.info)
    - Dla fazy "optimization": monitoruje BEZPOŚREDNIO bazę danych OptimizationRun
    Supports HTMX partial updates.
    """
    from denorm.models import DirtyInstance

    from ewaluacja_liczba_n.models import LiczbaNDlaUczelni

    task = AsyncResult(task_id)
    uczelnia = Uczelnia.objects.first()

    context = {
        "task_id": task_id,
        "dirty_count": DirtyInstance.objects.count(),
    }

    # KROK 1: Sprawdź fazę zadania z task.info (dla faz przed optymalizacją)
    task_info = task.info if task.info and isinstance(task.info, dict) else {}
    current_step = task_info.get("step", "unknown")

    logger.info(
        f"Checking optimize_unpin task {task_id}: current step={current_step}, task.info={task_info}"
    )

    # KROK 2: Obsłuż wczesne fazy (validation, snapshot, unpinning, denorm) bezpośrednio z task.info
    if current_step in ("validation", "snapshot"):
        return _handle_validation_or_snapshot_phase(
            request, task_id, current_step, task_info, context
        )

    if current_step == "unpinning":
        return _handle_unpinning_phase(request, task_id, task_info, context)

    if current_step == "denorm":
        return _handle_denorm_phase(request, task_id, task_info, context)

    # KROK 3: Monitoruj postęp przez bazę danych TYLKO dla fazy optimization
    raportowane_dyscypliny = LiczbaNDlaUczelni.objects.filter(
        uczelnia=uczelnia, liczba_n__gte=12
    ).select_related("dyscyplina_naukowa")

    discipline_count = raportowane_dyscypliny.count()
    dyscypliny_ids = list(
        raportowane_dyscypliny.values_list("dyscyplina_naukowa_id", flat=True)
    )

    completed_count = OptimizationRun.objects.filter(
        uczelnia=uczelnia,
        dyscyplina_naukowa_id__in=dyscypliny_ids,
        status="completed",
    ).count()

    running_count = OptimizationRun.objects.filter(
        uczelnia=uczelnia,
        dyscyplina_naukowa_id__in=dyscypliny_ids,
        status="running",
    ).count()

    percent_complete = (
        int((completed_count / discipline_count) * 100) if discipline_count > 0 else 0
    )

    logger.info(
        f"Task {task_id} monitoring: task.ready()={task.ready()}, "
        f"{completed_count}/{discipline_count} completed ({percent_complete}%), {running_count} running"
    )

    # KROK 4: Sprawdź czy wszystkie dane są zapisane w bazie
    all_data_complete = False
    if completed_count >= discipline_count and discipline_count > 0:
        logger.info(
            "All OptimizationRun records completed, verifying data integrity..."
        )
        all_data_complete = _verify_optimization_data_complete(
            raportowane_dyscypliny, uczelnia
        )

    # KROK 5: Określ stan na podstawie task.ready() i all_data_complete
    context_update = _determine_unpin_task_context(
        task,
        all_data_complete,
        completed_count,
        discipline_count,
        running_count,
        percent_complete,
    )
    context.update(context_update)

    # KROK 6: Jeśli zadanie się zakończyło pomyślnie i mamy success=True w kontekście
    if context.get("success"):
        return _handle_task_completion(request, context)

    # Jeśli zadanie zakończyło się błędem, też wyczyść status
    if context.get("error") and context.get("task_ready"):
        status = StatusOptymalizacjiZOdpinaniem.get_or_create()
        status.zakoncz(f"Błąd: {str(context.get('error', 'Nieznany błąd'))[:200]}")

    # If HTMX request, return only the progress partial
    template = (
        "ewaluacja_optymalizacja/_optimize_unpin_progress.html"
        if request.headers.get("HX-Request")
        else "ewaluacja_optymalizacja/optimize_unpin_status.html"
    )
    return render(request, template, context)


@login_required
@require_POST
def cancel_optimize_unpin_task(request, task_id):
    """
    Anuluje zadanie optymalizacji z odpinaniem.
    """
    from django_bpp.celery_tasks import app

    task = AsyncResult(task_id)

    # Sprawdź czy to jest aktualnie działające zadanie w bazie danych
    status = StatusOptymalizacjiZOdpinaniem.get_or_create()
    if not status.w_trakcie or status.task_id != task_id:
        messages.error(
            request,
            "Nie możesz anulować tego zadania - nie jest aktualnie uruchomione.",
        )
        return redirect("ewaluacja_optymalizacja:index")

    try:
        # Revoke the task (terminate if running)
        app.control.revoke(task_id, terminate=True)

        # Forget the result from backend (Redis)
        task.forget()

        # Clear from database
        status.zakoncz("Zadanie anulowane przez użytkownika")

        logger.info(f"Optimize-unpin task {task_id} cancelled by user {request.user}")
        messages.success(
            request, "Zadanie optymalizacji z odpinaniem zostało anulowane."
        )

    except Exception as e:
        logger.error(f"Failed to cancel optimize-unpin task {task_id}: {e}")
        messages.error(request, f"Nie udało się anulować zadania: {e}")

    return redirect("ewaluacja_optymalizacja:index")
