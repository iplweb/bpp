"""Widoki resetowania przypięć."""

import logging
from time import sleep

from celery.result import AsyncResult
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from bpp.models import Uczelnia

from .helpers import _get_discipline_pin_stats

logger = logging.getLogger(__name__)


@login_required
def reset_discipline_pins(request, pk):
    """
    Resetuje przypięcia dla danej dyscypliny (ustawia przypieta=True).
    Tworzy snapshot przed resetowaniem.
    """
    from denorm.models import DirtyInstance
    from denorm.tasks import flush_via_queue

    from bpp.models import (
        Autor_Dyscyplina,
        Dyscyplina_Naukowa,
        Patent_Autor,
        Wydawnictwo_Ciagle_Autor,
        Wydawnictwo_Zwarte_Autor,
    )
    from ewaluacja_liczba_n.models import LiczbaNDlaUczelni
    from snapshot_odpiec.models import SnapshotOdpiec

    from ..tasks import solve_single_discipline_task

    dyscyplina = get_object_or_404(Dyscyplina_Naukowa, pk=pk)

    # Sprawdź czy są odpięte rekordy
    stats = _get_discipline_pin_stats(dyscyplina)
    if stats["unpinned"] == 0:
        messages.warning(
            request,
            f"Dyscyplina '{dyscyplina.nazwa}' nie ma odpiętych rekordów w latach 2022-2025.",
        )
        return redirect("ewaluacja_optymalizacja:index")

    # Pobierz autorów którzy mają Autor_Dyscyplina w latach 2022-2025 dla tej dyscypliny
    autorzy_ids = set(
        Autor_Dyscyplina.objects.filter(
            rok__gte=2022,
            rok__lte=2025,
            dyscyplina_naukowa=dyscyplina,
        )
        .values_list("autor_id", flat=True)
        .distinct()
    )

    with transaction.atomic():
        # Utwórz snapshot przed resetowaniem
        snapshot = SnapshotOdpiec.objects.create(
            owner=request.user, comment=f"przed resetem przypięć - {dyscyplina.nazwa}"
        )

        logger.info(
            f"Created snapshot {snapshot.pk} before resetting pins for discipline "
            f"'{dyscyplina.nazwa}' (user: {request.user})"
        )

        # Resetuj przypięcia dla wszystkich modeli
        base_filter = Q(
            rekord__rok__gte=2022,
            rekord__rok__lte=2025,
            dyscyplina_naukowa=dyscyplina,
            autor_id__in=autorzy_ids,
        )

        updated_count = 0
        for model in [Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor, Patent_Autor]:
            count = model.objects.filter(base_filter).update(przypieta=True)
            updated_count += count
            logger.info(
                f"Reset {count} pins in {model.__name__} for discipline '{dyscyplina.nazwa}'"
            )

    # Poczekaj na zakończenie denormalizacji
    logger.info(
        f"Waiting for denormalization to complete after resetting pins for '{dyscyplina.nazwa}'"
    )

    # Trigger denorm processing via Celery queue
    flush_via_queue.delay()
    logger.info("Triggered denorm flush via queue")

    max_wait = 600  # Max 10 minut
    waited = 0
    check_interval = 5

    while DirtyInstance.objects.count() > 0 and waited < max_wait:
        sleep(check_interval)
        waited += check_interval
        dirty_count = DirtyInstance.objects.count()
        logger.info(
            f"Waiting for denormalization after reset... {dirty_count} objects remaining"
        )

    # Uruchom zadanie optymalizacji dla tej dyscypliny
    logger.info(f"Starting optimization for discipline '{dyscyplina.nazwa}'")

    uczelnia = Uczelnia.objects.first()

    try:
        liczba_n_obj = LiczbaNDlaUczelni.objects.get(
            uczelnia=uczelnia, dyscyplina_naukowa=dyscyplina
        )

        task = solve_single_discipline_task.delay(
            uczelnia.pk, dyscyplina.pk, float(liczba_n_obj.liczba_n)
        )

        logger.info(
            f"Started optimization task {task.id} for discipline '{dyscyplina.nazwa}'"
        )

        messages.success(
            request,
            f"Zresetowano {updated_count} przypięć dla dyscypliny '{dyscyplina.nazwa}' "
            f"(lata 2022-2025). Utworzono snapshot #{snapshot.pk}. "
            f"Trwa przeliczanie optymalizacji...",
        )
    except LiczbaNDlaUczelni.DoesNotExist:
        logger.warning(
            f"No LiczbaNDlaUczelni found for discipline '{dyscyplina.nazwa}', "
            "skipping optimization"
        )
        messages.success(
            request,
            f"Zresetowano {updated_count} przypięć dla dyscypliny '{dyscyplina.nazwa}' "
            f"(lata 2022-2025). Utworzono snapshot #{snapshot.pk}.",
        )

    return redirect("ewaluacja_optymalizacja:index")


@login_required
def reset_all_pins(request):
    """
    Uruchamia zadanie Celery do resetowania przypięć dla wszystkich autorów uczelni.
    Resetuje przypięcia dla rekordów 2022-2025 gdzie autor ma dyscyplinę.
    """
    from celery_singleton import DuplicateTaskError

    from ..tasks import reset_all_pins_task

    # Pobierz pierwszą uczelnię (zakładamy, że jest tylko jedna)
    uczelnia = Uczelnia.objects.first()

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
