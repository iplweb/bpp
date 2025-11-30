"""Widoki listy i szczegółów wyników optymalizacji."""

import logging

from django.contrib.auth.decorators import login_required
from django.db.models import Count, Q
from django.shortcuts import get_object_or_404, render

from ..models import OptimizationRun
from .helpers import _calculate_liczba_n_stats, _get_discipline_pin_stats

logger = logging.getLogger(__name__)


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
