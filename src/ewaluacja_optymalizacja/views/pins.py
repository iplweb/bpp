"""Widoki resetowania przypięć."""

import logging

from celery.result import AsyncResult
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render

from bpp.models import Uczelnia

from .helpers import _get_discipline_pin_stats

logger = logging.getLogger(__name__)


@login_required
def reset_discipline_pins(request, pk):
    """Zleca reset przypięć dyscypliny (2022-2025) + optymalizację w tle.

    Widok jest lekki: waliduje wejście, sprawdza czy jest co resetować, po
    czym uruchamia zadanie Celery i przekierowuje na stronę statusu. Cała
    ciężka część (snapshot, reset, oczekiwanie na denormalizację i
    optymalizacja) biegnie w workerze — wcześniej request blokował się tu
    do 10 minut, śpiąc w pętli i czekając także na cudzą denormalizację.
    """
    from celery_singleton import DuplicateTaskError

    from bpp.models import Dyscyplina_Naukowa

    from ..tasks import reset_discipline_pins_task

    dyscyplina = get_object_or_404(Dyscyplina_Naukowa, pk=pk)

    # Sprawdź czy jest w ogóle co resetować (szybki warunek, w requeście).
    stats = _get_discipline_pin_stats(dyscyplina)
    if stats["unpinned"] == 0:
        messages.warning(
            request,
            f"Dyscyplina '{dyscyplina.nazwa}' nie ma odpiętych rekordów "
            "w latach 2022-2025.",
        )
        return redirect("ewaluacja_optymalizacja:index")

    uczelnia = Uczelnia.objects.get_for_request(request)
    if not uczelnia:
        messages.error(request, "Nie znaleziono uczelni w systemie.")
        return redirect("ewaluacja_optymalizacja:index")

    try:
        task = reset_discipline_pins_task.delay(
            uczelnia.pk, dyscyplina.pk, request.user.pk
        )
    except DuplicateTaskError:
        messages.error(
            request,
            "Zadanie resetowania przypięć dla tej dyscypliny jest już "
            "uruchomione. Poczekaj na jego zakończenie.",
        )
        return redirect("ewaluacja_optymalizacja:index")

    logger.info(
        f"Zlecono reset przypięć dyscypliny '{dyscyplina.nazwa}' "
        f"(task {task.id}, user: {request.user})"
    )
    messages.success(
        request,
        f"Zlecono reset przypięć i optymalizację dla dyscypliny "
        f"'{dyscyplina.nazwa}'. Trwa przetwarzanie…",
    )
    return redirect("ewaluacja_optymalizacja:reset-all-pins-status", task_id=task.id)


@login_required
def reset_all_pins(request):
    """
    Uruchamia zadanie Celery do resetowania przypięć dla wszystkich autorów uczelni.
    Resetuje przypięcia dla rekordów 2022-2025 gdzie autor ma dyscyplinę.
    """
    from celery_singleton import DuplicateTaskError

    from ..tasks import reset_all_pins_task

    uczelnia = Uczelnia.objects.get_for_request(request)

    if not uczelnia:
        messages.error(request, "Nie znaleziono uczelni w systemie.")
        return redirect("ewaluacja_optymalizacja:index")

    logger.info(f"Starting reset all pins for {uczelnia}")

    # Uruchom zadanie Celery
    # Sprawdź czy nie ma już uruchomionego zadania
    try:
        task = reset_all_pins_task.delay(uczelnia.pk)
    except DuplicateTaskError:
        messages.error(
            request,
            "Zadanie resetowania przypięć jest już uruchomione. "
            "Poczekaj na zakończenie obecnego zadania.",
        )
        return redirect("ewaluacja_optymalizacja:index")

    # Przekieruj do strony statusu
    return redirect("ewaluacja_optymalizacja:reset-all-pins-status", task_id=task.id)


@login_required
def reset_all_pins_status(request, task_id):
    """
    Wyświetla status zadania resetowania przypięć dla wszystkich autorów.
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
        f"Checking reset_all_pins task {task_id}: current step={current_step}, "
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
        total_reset = result.get("total_reset", 0)

        messages.success(
            request,
            f"Reset przypięć zakończony pomyślnie! Zresetowano {total_reset} przypięć.",
        )

        # Dla HTMX requests używamy nagłówka HX-Redirect aby wykonać full-page redirect
        if request.headers.get("HX-Request"):
            from django.http import HttpResponse
            from django.urls import reverse

            response = HttpResponse(status=200)
            response["HX-Redirect"] = reverse("ewaluacja_optymalizacja:index")
            return response

        # Dla zwykłych requestów normalny redirect
        return redirect("ewaluacja_optymalizacja:index")

    # If HTMX request, return only the progress partial
    if request.headers.get("HX-Request"):
        return render(
            request,
            "ewaluacja_optymalizacja/_reset_all_pins_progress.html",
            context,
        )

    return render(
        request, "ewaluacja_optymalizacja/reset_all_pins_status.html", context
    )
