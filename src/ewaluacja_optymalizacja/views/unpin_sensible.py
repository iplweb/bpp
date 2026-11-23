"""Widoki odpinania sensownych możliwości."""

import logging
import uuid

from celery.result import AsyncResult
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect

from bpp.models import Uczelnia
from ewaluacja_common.okres import okres_dla_request

logger = logging.getLogger(__name__)


@login_required
def unpin_all_sensible(request):
    """
    Uruchamia zadanie Celery do odpinania wszystkich sensownych możliwości odpinania.
    Odpina rekordy gdzie makes_sense=True, czeka na denormalizację i przelicza metryki + unpinning.
    """
    from celery_singleton import DuplicateTaskError

    from ..models import StatusOdpinaniaWszystkich
    from ..tasks import unpin_all_sensible_task

    uczelnia = Uczelnia.objects.get_for_request(request)

    if not uczelnia:
        messages.error(request, "Nie znaleziono uczelni w systemie.")
        return redirect("ewaluacja_optymalizacja:unpinning-list")

    # Trwa już (albo wisi) poprzedni przebieg? ``aktualny()`` przy okazji
    # anuluje taki, nad którym nikt już nie pracuje.
    status = StatusOdpinaniaWszystkich.aktualny()
    if status.w_trakcie and status.task_id:
        if not AsyncResult(status.task_id).ready():
            messages.info(
                request,
                "Odpinanie sensownych możliwości już trwa. Przekierowuję do statusu.",
            )
            return redirect(
                "ewaluacja_optymalizacja:unpin-all-sensible-status",
                task_id=status.task_id,
            )
        # Zadanie skończyło pracę, a slot został — zwolnij go.
        StatusOdpinaniaWszystkich.zwolnij_slot(status.task_id)

    logger.info(f"Starting unpin all sensible for {uczelnia}")

    # Slot zajmujemy PRZED wysłaniem zadania, pod jego przyszłym
    # identyfikatorem: zadanie, które nigdy nie wystartuje (nie działa usługa
    # zadań, zadanie przepadło), zostawia wtedy ślad, który strażnik
    # przebiegów potrafi anulować. Samo zadanie wejdzie w ten sam slot.
    task_id = str(uuid.uuid4())
    if not StatusOdpinaniaWszystkich.sprobuj_zajac_slot(task_id, logger):
        messages.error(
            request,
            "Zadanie odpinania sensownych możliwości jest już uruchomione. "
            "Poczekaj na zakończenie obecnego zadania.",
        )
        return redirect("ewaluacja_optymalizacja:unpinning-list")

    try:
        task = unpin_all_sensible_task.apply_async(
            args=[uczelnia.pk],
            kwargs={"okres_pk": okres_dla_request(request).pk},
            task_id=task_id,
        )
    except DuplicateTaskError:
        StatusOdpinaniaWszystkich.zwolnij_slot(task_id)
        messages.error(
            request,
            "Zadanie odpinania sensownych możliwości jest już uruchomione. "
            "Poczekaj na zakończenie obecnego zadania.",
        )
        return redirect("ewaluacja_optymalizacja:unpinning-list")
    if str(task.id) != task_id:
        # Blokada singletona zwróciła już działające zadanie — nasz slot
        # był na wyrost.
        StatusOdpinaniaWszystkich.zwolnij_slot(task_id)

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

    from ..models import StatusOdpinaniaWszystkich
    from .helpers import kontekst_przerwanego_przebiegu, render_postepu

    przerwany = kontekst_przerwanego_przebiegu(StatusOdpinaniaWszystkich, task_id)

    # Zadanie padło w trakcie albo nie działa usługa zadań w tle
    if przerwany:
        context.update(przerwany)

    # Jeśli zadanie się nie zakończyło
    elif not task.ready():
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

    return render_postepu(
        request,
        "ewaluacja_optymalizacja/_unpin_all_sensible_progress.html",
        "ewaluacja_optymalizacja/unpin_all_sensible_status.html",
        context,
    )
