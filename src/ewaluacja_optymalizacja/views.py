import logging
from decimal import Decimal

from celery.result import AsyncResult
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, redirect, render

from bpp.models import Uczelnia

from .models import OptimizationRun
from .tasks import solve_all_reported_disciplines

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

    runs = OptimizationRun.objects.select_related(
        "dyscyplina_naukowa", "uczelnia"
    ).all()

    # Dla każdego run oblicz procent slotów poza N oraz statystyki przypięć
    runs_with_stats = []
    for run in runs:
        # Użyj _calculate_liczba_n_stats żeby dostać procent slotów poza N
        author_results = run.author_results.select_related("rodzaj_autora").all()
        stats = _calculate_liczba_n_stats(run, author_results)

        # Dodaj procent slotów poza N do obiektu run
        run.outside_n_slots_pct = stats["non_n_slots_pct"]

        # Dodaj statystyki przypięć dla dyscypliny
        run.pin_stats = _get_discipline_pin_stats(run.dyscyplina_naukowa)

        runs_with_stats.append(run)

    # Sprawdź czy są dane liczby N
    uczelnia = Uczelnia.objects.first()
    liczba_n_count = 0
    liczba_n_raportowane = 0

    if uczelnia:
        liczba_n_count = LiczbaNDlaUczelni.objects.filter(uczelnia=uczelnia).count()
        liczba_n_raportowane = LiczbaNDlaUczelni.objects.filter(
            uczelnia=uczelnia, liczba_n__gte=12
        ).count()

    # Oblicz agregacje dla ostatnich 10 wierszy (dla podsumowania w tabeli)
    recent_runs = runs_with_stats[:10]

    summary = {
        "total_points": Decimal("0"),
        "total_publications": 0,
        "total_low_mono_weighted": Decimal("0"),  # suma LOW-MONO % * liczba publikacji
        "total_outside_n_weighted": Decimal("0"),  # suma sloty poza N % * liczba slotów
        "total_publications_for_low_mono": 0,  # suma publikacji (dla średniej ważonej)
        "total_slots_for_outside_n": Decimal("0"),  # suma slotów (dla średniej ważonej)
        "total_pinned": 0,
        "total_unpinned": 0,
    }

    for run in recent_runs:
        summary["total_points"] += run.total_points
        summary["total_publications"] += run.total_publications
        summary["total_pinned"] += run.pin_stats["pinned"]
        summary["total_unpinned"] += run.pin_stats["unpinned"]

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

    # Oblicz procenty przypięte/odpięte
    total_pins = summary["total_pinned"] + summary["total_unpinned"]
    if total_pins > 0:
        summary["pinned_pct"] = (summary["total_pinned"] / total_pins) * 100
        summary["unpinned_pct"] = (summary["total_unpinned"] / total_pins) * 100
    else:
        summary["pinned_pct"] = Decimal("0")
        summary["unpinned_pct"] = Decimal("0")

    context = {
        "optimization_runs": runs_with_stats,
        "liczba_n_count": liczba_n_count,
        "liczba_n_raportowane": liczba_n_raportowane,
        "summary": summary,
        "dirty_count": dirty_count,
    }

    return render(request, "ewaluacja_optymalizacja/index.html", context)


@login_required
def run_list(request):
    """
    Lista wszystkich wykonanych optymalizacji
    """
    runs = OptimizationRun.objects.select_related(
        "dyscyplina_naukowa", "uczelnia"
    ).order_by("-started_at")

    # Dla każdego run oblicz procent slotów poza N oraz statystyki przypięć
    runs_with_stats = []
    for run in runs:
        # Użyj _calculate_liczba_n_stats żeby dostać procent slotów poza N
        author_results = run.author_results.select_related("rodzaj_autora").all()
        stats = _calculate_liczba_n_stats(run, author_results)

        # Dodaj procent slotów poza N do obiektu run
        run.outside_n_slots_pct = stats["non_n_slots_pct"]

        # Dodaj statystyki przypięć dla dyscypliny
        run.pin_stats = _get_discipline_pin_stats(run.dyscyplina_naukowa)

        runs_with_stats.append(run)

    return render(
        request, "ewaluacja_optymalizacja/run_list.html", {"runs": runs_with_stats}
    )


@login_required
def run_detail(request, pk):
    """
    Szczegółowy widok wyników optymalizacji z wizualizacją
    """
    run = get_object_or_404(
        OptimizationRun.objects.select_related("dyscyplina_naukowa", "uczelnia"), pk=pk
    )

    # Get author results with annotations
    author_results = (
        run.author_results.select_related("autor", "rodzaj_autora")
        .prefetch_related("publications")
        .annotate(
            pub_count=Count("publications"),
            low_mono_count=Count(
                "publications", filter=Q(publications__is_low_mono=True)
            ),
        )
    )

    # Check which authors have evaluation metrics for this discipline
    from ewaluacja_metryki.models import MetrykaAutora

    autor_ids = [ar.autor_id for ar in author_results]
    existing_metrics = set(
        MetrykaAutora.objects.filter(
            autor_id__in=autor_ids, dyscyplina_naukowa=run.dyscyplina_naukowa
        ).values_list("autor_id", flat=True)
    )

    # Add ma_metryke attribute to each author_result
    for author_result in author_results:
        author_result.ma_metryke = author_result.autor_id in existing_metrics

    # Calculate statistics for liczba N analysis
    stats = _calculate_liczba_n_stats(run, author_results)

    # Prepare data for charts
    chart_data = {
        "labels": ["Autorzy w liczbie N", "Autorzy poza liczbą N"],
        "points": [float(stats["n_points"]), float(stats["non_n_points"])],
        "slots": [float(stats["n_slots"]), float(stats["non_n_slots"])],
        "publications": [stats["n_pubs"], stats["non_n_pubs"]],
        "low_mono_data": {
            "labels": ["LOW-MONO", "Inne publikacje"],
            "values": [
                run.low_mono_count,
                run.total_publications - run.low_mono_count,
            ],
        },
    }

    context = {
        "run": run,
        "author_results": author_results,
        "stats": stats,
        "chart_data": chart_data,
    }

    return render(request, "ewaluacja_optymalizacja/run_detail.html", context)


@login_required
def discipline_comparison(request):
    """
    Porównanie wyników dla różnych dyscyplin
    """
    # Get latest run for each discipline

    latest_runs = {}
    all_runs = OptimizationRun.objects.filter(status="completed")

    for run in all_runs:
        disc_id = run.dyscyplina_naukowa_id
        if (
            disc_id not in latest_runs
            or run.started_at > latest_runs[disc_id].started_at
        ):
            latest_runs[disc_id] = run

    runs = list(latest_runs.values())
    runs.sort(key=lambda x: x.dyscyplina_naukowa.nazwa)

    # Calculate stats for each discipline
    discipline_stats = []
    for run in runs:
        author_results = run.author_results.select_related("rodzaj_autora")
        stats = _calculate_liczba_n_stats(run, author_results)
        stats["discipline"] = run.dyscyplina_naukowa.nazwa
        stats["run_id"] = run.pk
        stats["started_at"] = run.started_at

        # Convert Decimal values to proper float strings for JavaScript
        # This ensures we get dots instead of commas regardless of locale
        stats["n_points_js"] = str(float(stats["n_points"]))
        stats["non_n_points_js"] = str(float(stats["non_n_points"]))
        stats["n_slots_js"] = str(float(stats["n_slots"]))
        stats["non_n_slots_js"] = str(float(stats["non_n_slots"]))
        stats["n_slots_pct_js"] = str(float(stats["n_slots_pct"]))
        stats["non_n_slots_pct_js"] = str(float(stats["non_n_slots_pct"]))
        stats["low_mono_pct_js"] = str(float(stats["low_mono_pct"]))
        stats["non_n_and_low_mono_pct_js"] = str(float(stats["non_n_and_low_mono_pct"]))

        discipline_stats.append(stats)

    context = {
        "discipline_stats": discipline_stats,
    }

    return render(
        request, "ewaluacja_optymalizacja/discipline_comparison.html", context
    )


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


@login_required
def start_bulk_optimization(request):
    """
    Uruchamia zadanie Celery do optymalizacji wszystkich dyscyplin raportowanych.
    """
    from denorm.models import DirtyInstance

    from ewaluacja_liczba_n.models import LiczbaNDlaUczelni

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
            "Brak danych liczby N dla uczelni! Przed optymalizacją musisz najpierw policzyć liczbę N. "
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
    from ewaluacja_optymalizacja.models import OptimizationRun

    deleted_count = OptimizationRun.objects.filter(uczelnia=uczelnia).delete()[0]
    logger.info(
        f"Cleared {deleted_count} old OptimizationRun records for uczelnia {uczelnia.pk}"
    )

    logger.info(
        f"Starting bulk optimization for {uczelnia}: "
        f"{liczba_n_raportowane} disciplines with liczba_n >= 12"
    )

    # Uruchom zadanie Celery
    task = solve_all_reported_disciplines.delay(uczelnia.pk)

    # Nie pokazuj natychmiastowego komunikatu sukcesu - zadanie dopiero się rozpoczęło
    # Komunikat pojawi się na stronie statusu po faktycznym zakończeniu wszystkich operacji

    # Przekieruj do strony statusu (z uczelnia_id)
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
    from bpp.models import Uczelnia
    from ewaluacja_liczba_n.models import LiczbaNDlaUczelni
    from ewaluacja_optymalizacja.models import OptimizationAuthorResult, OptimizationRun

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
    completed_count = 0
    failed_count = 0
    running_count = 0
    pending_count = 0
    disciplines_info = []

    for liczba_n_obj in raportowane_dyscypliny:
        dyscyplina = liczba_n_obj.dyscyplina_naukowa

        # Znajdź najnowszy OptimizationRun dla tej dyscypliny
        opt_run = (
            OptimizationRun.objects.filter(
                uczelnia=uczelnia, dyscyplina_naukowa=dyscyplina
            )
            .order_by("-started_at")
            .first()
        )

        disc_info = {
            "dyscyplina_id": dyscyplina.pk,
            "dyscyplina_nazwa": dyscyplina.nazwa,
            "liczba_n": float(liczba_n_obj.liczba_n),
        }

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
                    completed_count += 1
                else:
                    # OptimizationRun completed ale brak danych - wciąż się zapisuje
                    disc_info["status"] = "running"
                    running_count += 1

            elif opt_run.status == "failed":
                disc_info["status"] = "failed"
                disc_info["error"] = opt_run.notes
                failed_count += 1

            else:  # status == "running"
                disc_info["status"] = "running"
                running_count += 1
        else:
            # Brak OptimizationRun - zadanie jeszcze nie utworzyło rekordu
            disc_info["status"] = "queued"
            pending_count += 1

        disciplines_info.append(disc_info)

    # Oblicz postęp
    finished_count = completed_count + failed_count
    progress = (
        int((finished_count / total_disciplines) * 100) if total_disciplines > 0 else 0
    )

    # Określ czy wszystkie zadania są zakończone
    all_done = finished_count == total_disciplines

    context = {
        "task_id": task_id,
        "uczelnia_id": uczelnia_id,
    }

    if all_done and completed_count > 0:
        # Zadania NAPRAWDĘ zakończone - przekieruj do strony głównej
        logger.info(
            f"Bulk optimization for {uczelnia} completed: "
            f"{completed_count} successful, {failed_count} failed"
        )

        messages.success(
            request,
            f"Przeliczanie ewaluacji zakończone pomyślnie! "
            f"Przeliczono {completed_count} dyscyplin.",
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
        # To NIE jest błąd - to oznacza że jesteśmy na POCZĄTKU po skasowaniu OptimizationRun
        # Ustaw task_ready=False aby pokazać ekran oczekiwania
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

    # If HTMX request, return only the progress partial
    if request.headers.get("HX-Request"):
        return render(
            request, "ewaluacja_optymalizacja/_bulk_optimization_progress.html", context
        )

    return render(
        request, "ewaluacja_optymalizacja/bulk_optimization_status.html", context
    )


@login_required
def optimize_with_unpinning(request):
    """
    Uruchamia zadanie Celery do optymalizacji z odpinaniem niewykazanych slotów.
    """
    from denorm.models import DirtyInstance

    from ewaluacja_liczba_n.models import LiczbaNDlaUczelni

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
                f"Dyscyplina {liczba_n_obj.dyscyplina_naukowa.nazwa} nie ma wykonanej optymalizacji. "
                "Najpierw uruchom 'Policz całą ewaluację'.",
            )
            return redirect("ewaluacja_optymalizacja:index")

    logger.info(f"Starting optimization with unpinning for {uczelnia}")

    # Uruchom zadanie Celery
    # Sprawdź czy nie ma już uruchomionego zadania
    from celery_singleton import DuplicateTaskError

    from .tasks import optimize_and_unpin_task

    try:
        task = optimize_and_unpin_task.delay(uczelnia.pk)
    except DuplicateTaskError:
        messages.error(
            request,
            "Zadanie optymalizacji z odpinaniem jest już uruchomione. "
            "Poczekaj na zakończenie obecnego zadania.",
        )
        return redirect("ewaluacja_optymalizacja:index")

    # Nie pokazuj komunikatu sukcesu - zadanie dopiero się rozpoczyna
    # Przekieruj od razu do strony statusu
    return redirect("ewaluacja_optymalizacja:optimize-unpin-status", task_id=task.id)


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
    from ewaluacja_optymalizacja.models import (
        OptimizationAuthorResult,
        OptimizationPublication,
        OptimizationRun,
    )

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
        f"Checking optimize_unpin task {task_id}: current step={current_step}, "
        f"task.info={task_info}"
    )

    # KROK 2: Jeśli jesteśmy w fazie denormalizacji - użyj task.info
    if current_step == "denorm":
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

        # If HTMX request, return only the progress partial
        if request.headers.get("HX-Request"):
            return render(
                request,
                "ewaluacja_optymalizacja/_optimize_unpin_progress.html",
                context,
            )
        return render(
            request, "ewaluacja_optymalizacja/optimize_unpin_status.html", context
        )

    # KROK 3: Monitoruj postęp przez bazę danych (niezależnie od stanu task)
    # Pobierz listę dyscyplin raportowanych
    raportowane_dyscypliny = LiczbaNDlaUczelni.objects.filter(
        uczelnia=uczelnia, liczba_n__gte=12
    ).select_related("dyscyplina_naukowa")

    discipline_count = raportowane_dyscypliny.count()
    dyscypliny_ids = list(
        raportowane_dyscypliny.values_list("dyscyplina_naukowa_id", flat=True)
    )

    # Sprawdź ile OptimizationRun jest już w bazie - BEZPOŚREDNIO z bazy, NIE przez Celery
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

    # Oblicz procent postępu
    if discipline_count > 0:
        percent_complete = int((completed_count / discipline_count) * 100)
    else:
        percent_complete = 0

    logger.info(
        f"Task {task_id} monitoring: task.ready()={task.ready()}, "
        f"{completed_count}/{discipline_count} completed ({percent_complete}%), "
        f"{running_count} running"
    )

    # KROK 4: Sprawdź czy wszystkie dane są zapisane w bazie
    all_data_complete = False
    if completed_count >= discipline_count and discipline_count > 0:
        # Wszystkie OptimizationRun są completed - weryfikuj dane
        logger.info(
            "All OptimizationRun records completed, verifying data integrity..."
        )

        all_data_complete = True
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
                # Sprawdź czy są wyniki autorów
                has_authors = OptimizationAuthorResult.objects.filter(
                    optimization_run=opt_run
                ).exists()

                # Sprawdź czy są publikacje
                has_publications = OptimizationPublication.objects.filter(
                    author_result__optimization_run=opt_run
                ).exists()

                if not (has_authors and has_publications):
                    logger.info(
                        f"Data not fully saved for "
                        f"{liczba_n_obj.dyscyplina_naukowa.nazwa}: "
                        f"authors={has_authors}, publications={has_publications}"
                    )
                    all_data_complete = False
                    break
            else:
                logger.warning(
                    f"No optimization run found for "
                    f"{liczba_n_obj.dyscyplina_naukowa.nazwa}"
                )
                all_data_complete = False
                break

    # KROK 5: Określ stan na podstawie task.ready() i all_data_complete
    if task.ready():
        # Task Celery się zakończył
        if task.failed():
            # Task się nie powiódł
            error_info = str(task.info)
            logger.error(f"Task {task_id} failed: {error_info}")
            context["error"] = error_info
            context["success"] = False
            context["task_ready"] = True
            context["task_state"] = "FAILURE"
        elif task.successful() and all_data_complete:
            # Task się powiódł i wszystkie dane są w bazie
            result = task.result
            logger.info(f"Task {task_id} successful, all data verified")
            context["result"] = result
            context["success"] = True
            context["task_ready"] = True
            context["task_state"] = "SUCCESS"
        else:
            # Task się powiódł ale dane jeszcze się zapisują
            context["task_ready"] = False
            context["task_state"] = "PROGRESS"
            context["info"] = {
                "step": "finalizing",
                "progress": 99,
                "message": "Finalizowanie zapisów do bazy danych...",
                "completed_optimizations": completed_count,
                "total_optimizations": discipline_count,
            }
    else:
        # Task wciąż trwa - monitoruj postęp
        context["task_ready"] = False
        context["task_state"] = "PROGRESS"

        if completed_count >= discipline_count and discipline_count > 0:
            # Wszystkie dane są zapisane ale task jeszcze trwa
            context["info"] = {
                "step": "finalizing",
                "progress": 99,
                "message": "Finalizowanie zadania...",
                "completed_optimizations": completed_count,
                "total_optimizations": discipline_count,
            }
        else:
            # Zadanie wciąż trwa - pokaż postęp z bazy danych
            progress = (
                min(65 + int((completed_count / discipline_count) * 30), 95)
                if discipline_count > 0
                else 65
            )

            context["info"] = {
                "step": "optimization",
                "progress": progress,
                "message": f"Przeliczono {completed_count} z {discipline_count} "
                f"dyscyplin ({percent_complete}%)",
                "running_optimizations": running_count,
                "completed_optimizations": completed_count,
                "total_optimizations": discipline_count,
            }

    # KROK 6: Jeśli zadanie się zakończyło pomyślnie i mamy success=True w kontekście
    # to znaczy że wszystko jest OK - przekieruj z flash message
    # WAŻNE: Dla HTMX używamy nagłówka HX-Redirect zamiast zwykłego redirect 302
    if context.get("success"):
        result = context.get("result", {})
        unpinned_total = result.get("unpinned_total", 0)

        messages.success(
            request,
            f"Optymalizacja z odpinaniem zakończona pomyślnie! "
            f"Odpiętych publikacji: {unpinned_total}",
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
            request, "ewaluacja_optymalizacja/_optimize_unpin_progress.html", context
        )

    return render(
        request, "ewaluacja_optymalizacja/optimize_unpin_status.html", context
    )


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


@login_required
def reset_discipline_pins(request, pk):
    """
    Resetuje przypięcia dla danej dyscypliny (ustawia przypieta=True).
    Tworzy snapshot przed resetowaniem.
    """
    from django.db import transaction

    from bpp.models import (
        Autor_Dyscyplina,
        Dyscyplina_Naukowa,
        Patent_Autor,
        Wydawnictwo_Ciagle_Autor,
        Wydawnictwo_Zwarte_Autor,
    )
    from snapshot_odpiec.models import SnapshotOdpiec

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

    from time import sleep

    from denorm.models import DirtyInstance

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

    from ewaluacja_liczba_n.models import LiczbaNDlaUczelni

    from .tasks import solve_single_discipline_task

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
            f"No LiczbaNDlaUczelni found for discipline '{dyscyplina.nazwa}', skipping optimization"
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
    # Pobierz pierwszą uczelnię (zakładamy, że jest tylko jedna)
    uczelnia = Uczelnia.objects.first()

    if not uczelnia:
        messages.error(request, "Nie znaleziono uczelni w systemie.")
        return redirect("ewaluacja_optymalizacja:index")

    logger.info(f"Starting reset all pins for {uczelnia}")

    # Uruchom zadanie Celery
    # Sprawdź czy nie ma już uruchomionego zadania
    from celery_singleton import DuplicateTaskError

    from .tasks import reset_all_pins_task

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
    from celery.result import AsyncResult
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
            f"Reset przypięć zakończony pomyślnie! "
            f"Zresetowano {total_reset} przypięć.",
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


@login_required
def denorm_progress(request):
    """
    Endpoint HTMX zwracający progress bar dla denormalizacji.
    Śledzi liczbę DirtyInstance i pokazuje postęp przeliczania.

    Parametry GET:
        initial: Początkowa liczba rekordów (opcjonalnie, do obliczenia procentu)
    """
    from denorm.models import DirtyInstance

    dirty_count = DirtyInstance.objects.count()

    # Pobierz initial_count z parametru GET
    initial_count = request.GET.get("initial")
    if initial_count:
        try:
            initial_count = int(initial_count)
        except (ValueError, TypeError):
            initial_count = None

    # Oblicz procent pozostały do przeliczenia i ukończony
    if initial_count and initial_count > 0:
        remaining_pct = (dirty_count / initial_count) * 100
        completed_pct = 100 - remaining_pct
    else:
        remaining_pct = 0
        completed_pct = 0

    # Pokaż komunikat o zakończeniu jeśli było initial_count > 0 a teraz dirty_count == 0
    show_completed = (
        dirty_count == 0 and initial_count is not None and initial_count > 0
    )

    context = {
        "dirty_count": dirty_count,
        "initial_count": initial_count,
        "remaining_pct": remaining_pct,
        "completed_pct": completed_pct,
        "show_completed": show_completed,
    }

    return render(request, "ewaluacja_optymalizacja/_denorm_progress.html", context)
