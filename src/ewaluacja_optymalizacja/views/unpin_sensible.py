"""Widoki odpinania sensownych możliwości."""

import logging

from celery.result import AsyncResult
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from bpp.models import Uczelnia

logger = logging.getLogger(__name__)


@login_required
def unpin_all_sensible(request):
    """
    Uruchamia zadanie Celery do odpinania wszystkich sensownych możliwości odpinania.
    Odpina rekordy gdzie makes_sense=True, czeka na denormalizację i przelicza metryki + unpinning.
    """
    from celery_singleton import DuplicateTaskError

    from ..tasks import unpin_all_sensible_task

    # Pobierz pierwszą uczelnię (zakładamy, że jest tylko jedna)
    uczelnia = Uczelnia.objects.first()

    if not uczelnia:
        messages.error(request, "Nie znaleziono uczelni w systemie.")
        return redirect("ewaluacja_optymalizacja:unpinning-list")

    logger.info(f"Starting unpin all sensible for {uczelnia}")

    # Uruchom zadanie Celery
    # Sprawdź czy nie ma już uruchomionego zadania
    try:
        task = unpin_all_sensible_task.delay(uczelnia.pk)
    except DuplicateTaskError:
        messages.error(
            request,
            "Zadanie odpinania sensownych możliwości jest już uruchomione. "
            "Poczekaj na zakończenie obecnego zadania.",
        )
        return redirect("ewaluacja_optymalizacja:unpinning-list")

    # Przekieruj do strony statusu
    return redirect(
        "ewaluacja_optymalizacja:unpin-all-sensible-status", task_id=task.id
    )


@login_required
def unpin_all_sensible_status(request, task_id):
    """
    Wyświetla status zadania odpinania wszystkich sensownych możliwości.
    Supports HTMX partial updates.
    """
    from denorm.models import DirtyInstance

    task = AsyncResult(task_id)

    context = {
        "task_id": task_id,
        "dirty_count": DirtyInstance.objects.count(),
    }

    # Pobierz informacje o zadaniu
    task_info = task.info if task.info and isinstance(task.info, dict) else {}
    current_step = task_info.get("step", "unknown")

    logger.info(
        f"Checking unpin_all_sensible task {task_id}: current step={current_step}, "
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
        unpinned_count = result.get("unpinned_count", 0)

        messages.success(
            request,
            f"Odpinanie sensownych możliwości zakończone pomyślnie! "
            f"Odpięto {unpinned_count} rekordów. "
            f"Metryki i analiza unpinning zostały przeliczone.",
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
            "ewaluacja_optymalizacja/_unpin_all_sensible_progress.html",
            context,
        )

    return render(
        request, "ewaluacja_optymalizacja/unpin_all_sensible_status.html", context
    )
