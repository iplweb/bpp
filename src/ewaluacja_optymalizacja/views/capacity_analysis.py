"""Widoki analizy capacity-based unpinning."""

import logging

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_POST

from bpp.models import Dyscyplina_Naukowa
from ewaluacja_liczba_n.models import LiczbaNDlaUczelni

from ..tasks.unpinning.capacity_analysis import (
    apply_unpinning,
    identify_unpinning_candidates,
)

logger = logging.getLogger(__name__)


def _get_reportable_disciplines():
    """Pobierz dyscypliny raportowane (liczba N >= 12)."""
    reportable = []
    for liczba_n in LiczbaNDlaUczelni.objects.select_related(
        "dyscyplina_naukowa"
    ).all():
        if liczba_n.liczba_n and liczba_n.liczba_n >= 12:
            reportable.append(liczba_n.dyscyplina_naukowa)
    return reportable


@login_required
def capacity_analysis_list(request):
    """
    Wyświetla listę dyscyplin z możliwością uruchomienia analizy capacity-based.
    """
    # Pobierz dyscypliny raportowane
    reportable_disciplines = _get_reportable_disciplines()

    # Dla każdej dyscypliny pobierz liczbę kandydatów (szybka analiza)
    discipline_stats = []
    for dyscyplina in reportable_disciplines:
        try:
            candidates = identify_unpinning_candidates(dyscyplina)
            total_slot_gain = sum(c.slot_gain for c in candidates)
            total_point_gain = sum(c.estimated_point_gain for c in candidates)
            total_to_unpin = sum(len(c.unpin_author_ids) for c in candidates)

            discipline_stats.append(
                {
                    "dyscyplina": dyscyplina,
                    "candidates_count": len(candidates),
                    "total_slot_gain": total_slot_gain,
                    "total_point_gain": total_point_gain,
                    "total_to_unpin": total_to_unpin,
                }
            )
        except Exception as e:
            logger.error(f"Błąd analizy dla {dyscyplina.nazwa}: {e}")
            discipline_stats.append(
                {
                    "dyscyplina": dyscyplina,
                    "candidates_count": 0,
                    "total_slot_gain": 0,
                    "total_point_gain": 0,
                    "total_to_unpin": 0,
                    "error": str(e),
                }
            )

    # Sortuj po szacowanym zysku punktów malejąco
    discipline_stats.sort(key=lambda x: x["total_point_gain"], reverse=True)

    # Oblicz podsumowanie
    summary = {
        "total_disciplines": len(discipline_stats),
        "total_candidates": sum(d["candidates_count"] for d in discipline_stats),
        "total_slot_gain": sum(d["total_slot_gain"] for d in discipline_stats),
        "total_point_gain": sum(d["total_point_gain"] for d in discipline_stats),
        "total_to_unpin": sum(d["total_to_unpin"] for d in discipline_stats),
    }

    context = {
        "discipline_stats": discipline_stats,
        "summary": summary,
    }

    return render(
        request, "ewaluacja_optymalizacja/capacity_analysis_list.html", context
    )


@login_required
def capacity_analysis_detail(request, dyscyplina_pk):
    """
    Wyświetla szczegółową analizę capacity-based dla wybranej dyscypliny.
    """
    try:
        dyscyplina = Dyscyplina_Naukowa.objects.get(pk=dyscyplina_pk)
    except Dyscyplina_Naukowa.DoesNotExist:
        messages.error(request, "Nie znaleziono dyscypliny.")
        return redirect("ewaluacja_optymalizacja:capacity-analysis-list")

    # Uruchom analizę
    candidates = identify_unpinning_candidates(dyscyplina)

    # Oblicz podsumowanie
    total_slot_gain = sum(c.slot_gain for c in candidates)
    total_point_gain = sum(c.estimated_point_gain for c in candidates)
    total_to_unpin = sum(len(c.unpin_author_ids) for c in candidates)

    summary = {
        "candidates_count": len(candidates),
        "total_slot_gain": total_slot_gain,
        "total_point_gain": total_point_gain,
        "total_to_unpin": total_to_unpin,
    }

    context = {
        "dyscyplina": dyscyplina,
        "candidates": candidates,
        "summary": summary,
    }

    return render(
        request, "ewaluacja_optymalizacja/capacity_analysis_detail.html", context
    )


@login_required
@require_POST
def capacity_analysis_apply(request, dyscyplina_pk):
    """
    Zastosuj rekomendacje capacity-based unpinning dla wybranej dyscypliny.
    """
    from denorm import denorms

    try:
        dyscyplina = Dyscyplina_Naukowa.objects.get(pk=dyscyplina_pk)
    except Dyscyplina_Naukowa.DoesNotExist:
        messages.error(request, "Nie znaleziono dyscypliny.")
        return redirect("ewaluacja_optymalizacja:capacity-analysis-list")

    # Uruchom analizę
    candidates = identify_unpinning_candidates(dyscyplina)

    if not candidates:
        messages.warning(request, "Brak kandydatów do odpięcia.")
        return redirect(
            "ewaluacja_optymalizacja:capacity-analysis-detail",
            dyscyplina_pk=dyscyplina_pk,
        )

    # Zastosuj unpinning
    with transaction.atomic():
        result = apply_unpinning(candidates, dyscyplina, dry_run=False)

    # Flush denorms
    denorms.flush()

    messages.success(
        request,
        f"Zastosowano unpinning dla dyscypliny '{dyscyplina.nazwa}': "
        f"odpięto {result['unpinned_count']} przypisań w "
        f"{result['total_candidates']} publikacjach.",
    )

    if result["errors"]:
        for error in result["errors"][:5]:  # Pokaż max 5 błędów
            messages.warning(request, error)

    return redirect(
        "ewaluacja_optymalizacja:capacity-analysis-detail",
        dyscyplina_pk=dyscyplina_pk,
    )


@login_required
@require_POST
def capacity_analysis_apply_all(request):
    """
    Zastosuj rekomendacje capacity-based unpinning dla WSZYSTKICH dyscyplin.
    """
    from denorm import denorms

    reportable_disciplines = _get_reportable_disciplines()

    total_unpinned = 0
    total_candidates = 0
    errors = []

    with transaction.atomic():
        for dyscyplina in reportable_disciplines:
            try:
                candidates = identify_unpinning_candidates(dyscyplina)
                if candidates:
                    result = apply_unpinning(candidates, dyscyplina, dry_run=False)
                    total_unpinned += result["unpinned_count"]
                    total_candidates += result["total_candidates"]
                    errors.extend(result["errors"])
            except Exception as e:
                logger.error(f"Błąd przy unpinning dla {dyscyplina.nazwa}: {e}")
                errors.append(f"{dyscyplina.nazwa}: {str(e)}")

    # Flush denorms
    denorms.flush()

    messages.success(
        request,
        f"Zastosowano unpinning dla wszystkich dyscyplin: "
        f"odpięto {total_unpinned} przypisań w {total_candidates} publikacjach.",
    )

    if errors:
        for error in errors[:5]:
            messages.warning(request, error)
        if len(errors) > 5:
            messages.warning(request, f"... i {len(errors) - 5} więcej błędów")

    return redirect("ewaluacja_optymalizacja:capacity-analysis-list")
