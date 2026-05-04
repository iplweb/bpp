"""Helpers do podsumowania dyscyplin i opcji filtrów przeglądarki."""

from bpp.models import Dyscyplina_Naukowa

from ...models import OptimizationRun


def _get_reported_disciplines(uczelnia):
    """Pobierz ID raportowanych dyscyplin (liczba_n >= 12)."""
    from ewaluacja_liczba_n.models import LiczbaNDlaUczelni

    return list(
        LiczbaNDlaUczelni.objects.filter(
            uczelnia=uczelnia, liczba_n__gte=12
        ).values_list("dyscyplina_naukowa_id", flat=True)
    )


def _snapshot_discipline_points(uczelnia):
    """Zapisz aktualną punktację dyscyplin do obliczenia diff."""
    result = {}
    for opt_run in OptimizationRun.objects.filter(
        uczelnia=uczelnia,
        status="completed",
    ):
        result[str(opt_run.dyscyplina_naukowa_id)] = float(opt_run.total_points)
    return result


def _get_discipline_summary(uczelnia, punkty_przed=None, show_diff=True):
    """Pobierz podsumowanie dyscyplin z punktacją i opcjonalnym diff.

    Args:
        uczelnia: Instancja Uczelni
        punkty_przed: Dict {discipline_id: points} przed zmianą
        show_diff: Czy pokazywać diff (False gdy przeliczanie w trakcie)
    """
    from django.db.models import OuterRef, Subquery

    from ewaluacja_liczba_n.models import LiczbaNDlaUczelni

    punkty_przed = punkty_przed or {}
    # Obliczaj diff tylko gdy show_diff=True (czyli po zakończeniu wszystkich tasków)
    calculate_diff = show_diff and bool(punkty_przed)

    raportowane = (
        LiczbaNDlaUczelni.objects.filter(
            uczelnia=uczelnia,
            liczba_n__gte=12,
        )
        .select_related("dyscyplina_naukowa")
        .order_by("dyscyplina_naukowa__nazwa")
    )

    # Pre-fetch latest OptimizationRun per discipline (single query)
    reported_disc_ids = list(
        raportowane.values_list("dyscyplina_naukowa_id", flat=True)
    )

    latest_run_subquery = (
        OptimizationRun.objects.filter(
            uczelnia=uczelnia,
            dyscyplina_naukowa_id=OuterRef("dyscyplina_naukowa_id"),
            status="completed",
        )
        .order_by("-started_at")
        .values("pk")[:1]
    )

    opt_runs = OptimizationRun.objects.filter(
        uczelnia=uczelnia,
        status="completed",
        dyscyplina_naukowa_id__in=reported_disc_ids,
        pk__in=Subquery(
            OptimizationRun.objects.filter(
                uczelnia=uczelnia,
                status="completed",
                dyscyplina_naukowa_id__in=reported_disc_ids,
            )
            .annotate(latest_pk=Subquery(latest_run_subquery))
            .values("latest_pk")
        ),
    )

    opt_runs_by_disc = {r.dyscyplina_naukowa_id: r for r in opt_runs}

    summary = []
    total_points = 0
    total_slots = 0
    total_diff = 0

    for ln in raportowane:
        disc_id = ln.dyscyplina_naukowa_id
        opt_run = opt_runs_by_disc.get(disc_id)

        current_points = float(opt_run.total_points) if opt_run else 0
        current_slots = (
            float(opt_run.total_slots) if opt_run and opt_run.total_slots else 0
        )
        before_points = punkty_przed.get(str(disc_id), 0) if calculate_diff else 0
        diff = current_points - before_points if calculate_diff else 0

        total_points += current_points
        total_slots += current_slots
        total_diff += diff

        summary.append(
            {
                "dyscyplina": ln.dyscyplina_naukowa,
                "punkty": current_points,
                "slots": current_slots,
                "diff": diff,
                "has_diff": calculate_diff and before_points > 0,
            }
        )

    return {
        "disciplines": summary,
        "total_points": total_points,
        "total_slots": total_slots,
        "total_diff": total_diff,
        "has_diff": calculate_diff,
    }


def _get_filter_options(uczelnia):
    """Pobierz opcje dla filtrów."""
    reported_ids = _get_reported_disciplines(uczelnia)

    dyscypliny = Dyscyplina_Naukowa.objects.filter(pk__in=reported_ids).order_by(
        "nazwa"
    )

    return {
        "dyscypliny": dyscypliny,
        "lata": [2022, 2023, 2024, 2025],
    }
