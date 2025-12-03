"""Widoki masowej optymalizacji wszystkich dyscyplin."""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from bpp.models import Uczelnia

from ..models import (
    OptimizationAuthorResult,
    OptimizationRun,
    StatusOptymalizacjiBulk,
)
from ..tasks import solve_all_reported_disciplines

logger = logging.getLogger(__name__)


def _process_discipline_optimization_status(liczba_n_obj, uczelnia):
    """Process optimization status for a single discipline.

    Returns dict with discipline info including status, points, publications, etc.
    """
    dyscyplina = liczba_n_obj.dyscyplina_naukowa

    disc_info = {
        "dyscyplina_id": dyscyplina.pk,
        "dyscyplina_nazwa": dyscyplina.nazwa,
        "liczba_n": float(liczba_n_obj.liczba_n),
    }

    # Znajdź najnowszy OptimizationRun dla tej dyscypliny
    opt_run = (
        OptimizationRun.objects.filter(uczelnia=uczelnia, dyscyplina_naukowa=dyscyplina)
        .order_by("-started_at")
        .first()
    )

    if opt_run:
        if opt_run.status == "completed":
            # Sprawdź czy są zapisane dane autorów
            has_authors = OptimizationAuthorResult.objects.filter(
                optimization_run=opt_run
            ).exists()

            if has_authors:
                disc_info["status"] = "completed"
                disc_info["optimization_run_id"] = opt_run.pk
                disc_info["total_points"] = float(opt_run.total_points)
                disc_info["total_publications"] = opt_run.total_publications
                return disc_info, "completed"

            # OptimizationRun completed ale brak danych - wciąż się zapisuje
            disc_info["status"] = "running"
            return disc_info, "running"

        if opt_run.status == "failed":
            disc_info["status"] = "failed"
            disc_info["error"] = opt_run.notes
            return disc_info, "failed"

        # status == "running"
        disc_info["status"] = "running"
        return disc_info, "running"

    # Brak OptimizationRun - zadanie jeszcze nie utworzyło rekordu
    disc_info["status"] = "pending"
    return disc_info, "pending"


def _build_bulk_progress_context(
    task_id, uczelnia_id, uczelnia, total_disciplines, disciplines_info, status_counts
):
    """Build context dict based on optimization progress status."""
    completed_count = status_counts["completed"]
    failed_count = status_counts["failed"]
    running_count = status_counts["running"]
    pending_count = status_counts["pending"]

    finished_count = completed_count + failed_count
    progress = (
        int((finished_count / total_disciplines) * 100) if total_disciplines > 0 else 0
    )

    all_done = finished_count == total_disciplines

    context = {
        "task_id": task_id,
        "uczelnia_id": uczelnia_id,
    }

    if all_done and completed_count > 0:
        # Zadania NAPRAWDĘ zakończone
        logger.info(
            f"Bulk optimization for {uczelnia} completed: "
            f"{completed_count} successful, {failed_count} failed"
        )
        context["redirect_to_index"] = True
        context["success_message"] = (
            f"Przeliczanie ewaluacji zakończone pomyślnie! "
            f"Przeliczono {completed_count} dyscyplin."
        )
    elif all_done and total_disciplines == 0:
        # Brak dyscyplin do przetworzenia
        context["task_ready"] = True
        context["success"] = False
        context["task_state"] = "FAILURE"
        context["error"] = (
            "Brak dyscyplin do przetworzenia. "
            "Upewnij się, że istnieją dane LiczbaNDlaUczelni z liczbą N >= 12."
        )
        logger.warning(f"Bulk optimization for {uczelnia}: no disciplines to process")
    elif all_done and completed_count == 0 and failed_count == 0:
        # Wszystkie skończone ale nic nie wykonano - zadania nie wystartowały
        context["task_ready"] = False
        context["task_state"] = "PENDING"
        context["info"] = {
            "step": "optimizing",
            "progress": 0,
            "message": "Oczekiwanie na rozpoczęcie przetwarzania...",
            "total_disciplines": total_disciplines,
            "completed": 0,
            "failed": 0,
            "running": 0,
            "pending": total_disciplines,
            "disciplines": disciplines_info,
        }
        logger.info(f"Bulk optimization for {uczelnia}: waiting for tasks to start")
    else:
        # Zadania w trakcie
        context["task_ready"] = False
        context["task_state"] = "PROGRESS"
        context["info"] = {
            "step": "optimizing",
            "progress": progress,
            "message": f"Przetwarzanie dyscyplin: {finished_count}/{total_disciplines}",
            "total_disciplines": total_disciplines,
            "completed": completed_count,
            "failed": failed_count,
            "running": running_count,
            "pending": pending_count,
            "disciplines": disciplines_info,
        }
        logger.debug(
            f"Bulk optimization progress for {uczelnia}: "
            f"{finished_count}/{total_disciplines} ({progress}%)"
        )

    return context


@login_required
def start_bulk_optimization(request):
    """
    Uruchamia zadanie Celery do optymalizacji wszystkich dyscyplin raportowanych.
    """
    from denorm.models import DirtyInstance

    from ewaluacja_liczba_n.models import LiczbaNDlaUczelni

    # Użyj transakcji z blokadą wiersza aby zapobiec race condition
    # gdy dwóch użytkowników kliknie przycisk jednocześnie
    with transaction.atomic():
        # Sprawdź czy zadanie już działa (przez model singleton z blokadą)
        status, _ = StatusOptymalizacjiBulk.objects.select_for_update().get_or_create(
            pk=1
        )
        if status.w_trakcie and status.task_id and status.uczelnia:
            messages.info(
                request,
                "Zadanie optymalizacji już działa. Przekierowuję do statusu.",
            )
            return redirect(
                "ewaluacja_optymalizacja:bulk-status",
                uczelnia_id=status.uczelnia.pk,
                task_id=status.task_id,
            )

        # Sprawdź czy są rekordy do przeliczenia
        dirty_count = DirtyInstance.objects.count()
        if dirty_count > 0:
            messages.warning(
                request,
                f"Przed optymalizacją poczekaj na przeliczenie punktów. "
                f"Obecnie jest {dirty_count} rekordów do przeliczenia.",
            )
            return redirect("ewaluacja_optymalizacja:index")

        # Pobierz pierwszą uczelnię (zakładamy, że jest tylko jedna)
        uczelnia = Uczelnia.objects.first()

        if not uczelnia:
            messages.error(request, "Nie znaleziono uczelni w systemie.")
            return redirect("ewaluacja_optymalizacja:index")

        # WALIDACJA: Sprawdź czy istnieją dane liczby N dla uczelni
        liczba_n_count = LiczbaNDlaUczelni.objects.filter(uczelnia=uczelnia).count()
        liczba_n_raportowane = LiczbaNDlaUczelni.objects.filter(
            uczelnia=uczelnia, liczba_n__gte=12
        ).count()

        if liczba_n_count == 0:
            messages.error(
                request,
                "Brak danych liczby N dla uczelni! Przed optymalizacją musisz "
                "najpierw policzyć liczbę N. "
                'Przejdź do <a href="/ewaluacja_liczba_n/">modułu Liczba N</a> '
                "lub uruchom polecenie: python src/manage.py przelicz_n",
            )
            return redirect("ewaluacja_optymalizacja:index")

        if liczba_n_raportowane == 0:
            messages.warning(
                request,
                f"Znaleziono {liczba_n_count} dyscyplin z danymi liczby N, "
                "ale żadna nie ma liczby N >= 12 (nie są raportowane). "
                "Optymalizacja nie przetworzy żadnych dyscyplin.",
            )
            return redirect("ewaluacja_optymalizacja:index")

        # Skasuj stare rekordy OptimizationRun dla tej uczelni
        deleted_count = OptimizationRun.objects.filter(uczelnia=uczelnia).delete()[0]
        logger.info(
            f"Cleared {deleted_count} old OptimizationRun records for uczelnia "
            f"{uczelnia.pk}"
        )

        # Pobierz wybrany tryb algorytmu z formularza (domyślnie two-phase)
        algorithm_mode = request.POST.get("algorithm_mode", "two-phase")
        if algorithm_mode not in ["two-phase", "single-phase"]:
            algorithm_mode = "two-phase"  # fallback to default

        logger.info(
            f"Starting bulk optimization for {uczelnia}: "
            f"{liczba_n_raportowane} disciplines with liczba_n >= 12, "
            f"algorithm mode: {algorithm_mode}"
        )

        # Uruchom zadanie Celery
        task = solve_all_reported_disciplines.delay(uczelnia.pk, algorithm_mode)

        # Zapisz status w modelu singleton - WEWNĄTRZ TRANSAKCJI
        # aby drugi request widział zaktualizowany status
        status.rozpocznij(task_id=str(task.id), uczelnia=uczelnia)

    # Nie pokazuj natychmiastowego komunikatu sukcesu - zadanie dopiero się rozpoczęło
    # Komunikat pojawi się na stronie statusu po faktycznym zakończeniu wszystkich operacji

    # Przekieruj do strony statusu (z uczelnia_id) - poza transakcją
    return redirect(
        "ewaluacja_optymalizacja:bulk-status", uczelnia_id=uczelnia.pk, task_id=task.id
    )


@login_required
def bulk_optimization_status(request, uczelnia_id, task_id):
    """
    Wyświetla status zadania masowej optymalizacji.
    Sprawdza postęp poprzez zapytania do bazy danych zamiast monitorowania Celery.
    Supports HTMX partial updates.
    """
    from ewaluacja_liczba_n.models import LiczbaNDlaUczelni

    try:
        uczelnia = Uczelnia.objects.get(pk=uczelnia_id)
    except Uczelnia.DoesNotExist:
        context = {
            "task_id": task_id,
            "task_ready": True,
            "success": False,
            "error": f"Nie znaleziono uczelni o ID {uczelnia_id}",
        }
        if request.headers.get("HX-Request"):
            return render(
                request,
                "ewaluacja_optymalizacja/_bulk_optimization_progress.html",
                context,
            )
        return render(
            request, "ewaluacja_optymalizacja/bulk_optimization_status.html", context
        )

    # Pobierz listę dyscyplin raportowanych dla uczelni
    raportowane_dyscypliny = LiczbaNDlaUczelni.objects.filter(
        uczelnia=uczelnia, liczba_n__gte=12
    ).select_related("dyscyplina_naukowa")

    total_disciplines = raportowane_dyscypliny.count()

    if total_disciplines == 0:
        context = {
            "task_id": task_id,
            "task_ready": True,
            "success": True,
            "result": {
                "uczelnia_nazwa": str(uczelnia),
                "total_disciplines": 0,
                "successful": 0,
                "failed": 0,
                "disciplines": [],
            },
        }
        if request.headers.get("HX-Request"):
            return render(
                request,
                "ewaluacja_optymalizacja/_bulk_optimization_progress.html",
                context,
            )
        return render(
            request, "ewaluacja_optymalizacja/bulk_optimization_status.html", context
        )

    # Sprawdź status każdej dyscypliny w bazie danych
    status_counts = {"completed": 0, "failed": 0, "running": 0, "pending": 0}
    disciplines_info = []

    for liczba_n_obj in raportowane_dyscypliny:
        disc_info, status = _process_discipline_optimization_status(
            liczba_n_obj, uczelnia
        )
        status_counts[status] += 1
        disciplines_info.append(disc_info)

    # Build context based on progress
    context = _build_bulk_progress_context(
        task_id,
        uczelnia_id,
        uczelnia,
        total_disciplines,
        disciplines_info,
        status_counts,
    )

    # Handle redirect for completed tasks
    if context.get("redirect_to_index"):
        # Wyczyść status w modelu singleton - zadanie zakończone
        status = StatusOptymalizacjiBulk.get_or_create()

        # Wygeneruj ZIP ze wszystkimi XLS przed zakończeniem
        from .exports import generate_all_disciplines_zip_file

        logger.info("Generating ZIP file with all XLS files...")
        generate_all_disciplines_zip_file(status)

        status.zakoncz("Optymalizacja zakończona pomyślnie")

        messages.success(request, context["success_message"])

        if request.headers.get("HX-Request"):
            from django.http import HttpResponse
            from django.urls import reverse

            response = HttpResponse(status=200)
            response["HX-Redirect"] = reverse("ewaluacja_optymalizacja:index")
            return response

        return redirect("ewaluacja_optymalizacja:index")

    # If HTMX request, return only the progress partial
    if request.headers.get("HX-Request"):
        return render(
            request, "ewaluacja_optymalizacja/_bulk_optimization_progress.html", context
        )

    return render(
        request, "ewaluacja_optymalizacja/bulk_optimization_status.html", context
    )


@login_required
@require_POST
def cancel_bulk_optimization(request, uczelnia_id, task_id):
    """
    Anuluje zadanie masowej optymalizacji.
    """
    from celery.result import AsyncResult

    from django_bpp.celery_tasks import app

    # Sprawdź czy to jest aktualnie działające zadanie w bazie danych
    status = StatusOptymalizacjiBulk.get_or_create()
    if not status.w_trakcie or status.task_id != task_id:
        messages.error(
            request,
            "Nie możesz anulować tego zadania - nie jest aktualnie uruchomione.",
        )
        return redirect("ewaluacja_optymalizacja:index")

    try:
        # Revoke the task (terminate if running)
        task = AsyncResult(task_id)
        app.control.revoke(task_id, terminate=True)

        # Forget the result from backend (Redis)
        task.forget()

        # Mark running OptimizationRun records as failed
        running_runs = OptimizationRun.objects.filter(
            uczelnia_id=uczelnia_id,
            status="running",
        )
        running_runs.update(status="failed", notes="Anulowane przez użytkownika")

        # Clear from database
        status.zakoncz("Zadanie anulowane przez użytkownika")

        logger.info(
            f"Bulk optimization task {task_id} cancelled by user {request.user}"
        )
        messages.success(request, "Zadanie optymalizacji zostało anulowane.")

    except Exception as e:
        logger.error(f"Failed to cancel bulk optimization task {task_id}: {e}")
        messages.error(request, f"Nie udało się anulować zadania: {e}")

    return redirect("ewaluacja_optymalizacja:index")
