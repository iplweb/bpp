"""Tests for ewaluacja_optymalizacja Celery tasks."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest

from ewaluacja_optymalizacja.models import (
    OptimizationRun,
)
from ewaluacja_optymalizacja.tasks import (
    reset_all_pins_task,
    solve_all_reported_disciplines,
    solve_single_discipline_task,
    unpin_all_sensible_task,
)

# ============================================================================
# solve_single_discipline_task tests
# ============================================================================


@pytest.mark.django_db
def test_solve_single_discipline_task_success(uczelnia, dyscyplina1):
    """Test solve_single_discipline_task completes successfully."""
    mock_results = MagicMock()
    mock_results.total_points = 100.0
    mock_results.total_slots = 10.0
    mock_results.total_publications = 5
    mock_results.low_mono_count = 2
    mock_results.low_mono_percentage = 40.0
    mock_results.validation_passed = True
    mock_results.is_optimal = True
    mock_results.authors = {}

    with patch(
        "ewaluacja_optymalizacja.tasks.optimization.solve_discipline",
        return_value=mock_results,
    ):
        result = solve_single_discipline_task.apply(
            args=(uczelnia.pk, dyscyplina1.pk, 12.0, "two-phase")
        ).result

    assert result["status"] == "completed"
    assert result["dyscyplina_id"] == dyscyplina1.pk
    assert result["total_points"] == 100.0

    opt_run = OptimizationRun.objects.filter(dyscyplina_naukowa=dyscyplina1).first()
    assert opt_run is not None
    assert opt_run.status == "completed"
    assert opt_run.total_points == Decimal("100.0")


@pytest.mark.django_db
def test_solve_single_discipline_task_deletes_old_runs(uczelnia, dyscyplina1):
    """Test solve_single_discipline_task deletes old optimization runs."""
    old_run = OptimizationRun.objects.create(
        dyscyplina_naukowa=dyscyplina1,
        uczelnia=uczelnia,
        status="completed",
        total_points=Decimal("50.0"),
    )

    mock_results = MagicMock()
    mock_results.total_points = 100.0
    mock_results.total_slots = 10.0
    mock_results.total_publications = 5
    mock_results.low_mono_count = 0
    mock_results.low_mono_percentage = 0.0
    mock_results.validation_passed = True
    mock_results.is_optimal = True
    mock_results.authors = {}

    with patch(
        "ewaluacja_optymalizacja.tasks.optimization.solve_discipline",
        return_value=mock_results,
    ):
        solve_single_discipline_task.apply(
            args=(uczelnia.pk, dyscyplina1.pk, 12.0, "two-phase")
        )

    assert not OptimizationRun.objects.filter(pk=old_run.pk).exists()


@pytest.mark.django_db
def test_solve_single_discipline_task_handles_error(uczelnia, dyscyplina1):
    """Test solve_single_discipline_task handles errors gracefully."""
    with patch(
        "ewaluacja_optymalizacja.tasks.optimization.solve_discipline",
        side_effect=Exception("Solver error"),
    ):
        result = solve_single_discipline_task.apply(
            args=(uczelnia.pk, dyscyplina1.pk, 12.0, "two-phase")
        ).result

    assert result["status"] == "failed"
    assert "Solver error" in result["error"]

    opt_run = OptimizationRun.objects.filter(dyscyplina_naukowa=dyscyplina1).first()
    assert opt_run is not None
    assert opt_run.status == "failed"


@pytest.mark.django_db
def test_solve_single_discipline_task_timeout(uczelnia, dyscyplina1):
    """Test solve_single_discipline_task handles timeout."""
    from celery.exceptions import SoftTimeLimitExceeded

    with patch(
        "ewaluacja_optymalizacja.tasks.optimization.solve_discipline",
        side_effect=SoftTimeLimitExceeded(),
    ):
        result = solve_single_discipline_task.apply(
            args=(uczelnia.pk, dyscyplina1.pk, 12.0, "two-phase")
        ).result

    assert result["status"] == "failed"
    assert "limit czasu" in result["error"]


# ============================================================================
# solve_all_reported_disciplines tests
# ============================================================================


@pytest.mark.django_db
def test_solve_all_reported_disciplines_no_disciplines(uczelnia):
    """Test solve_all_reported_disciplines with no reported disciplines."""
    result = solve_all_reported_disciplines.apply(args=(uczelnia.pk,)).result

    assert result["uczelnia_id"] == uczelnia.pk
    assert result["total_disciplines"] == 0


# ============================================================================
# reset_all_pins_task tests
# ============================================================================


@pytest.mark.django_db
def test_reset_all_pins_task_creates_snapshot(
    uczelnia, dyscyplina1, autor_jan_kowalski
):
    """Test reset_all_pins_task creates SnapshotOdpiec."""
    from bpp.models import Autor_Dyscyplina
    from snapshot_odpiec.models import SnapshotOdpiec

    initial_count = SnapshotOdpiec.objects.count()

    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, dyscyplina_naukowa=dyscyplina1, rok=2023
    )

    with patch("ewaluacja_optymalizacja.tasks.reset_pins._wait_for_denorm"):
        with patch("ewaluacja_optymalizacja.tasks.reset_pins._run_bulk_optimization"):
            result = reset_all_pins_task.apply(args=(uczelnia.pk,)).result

    assert result["uczelnia_id"] == uczelnia.pk
    assert "snapshot_id" in result
    assert SnapshotOdpiec.objects.count() == initial_count + 1


@pytest.mark.django_db
def test_reset_all_pins_task_resets_pins(
    uczelnia, dyscyplina1, autor_jan_kowalski, wydawnictwo_ciagle, jednostka
):
    """Test reset_all_pins_task resets pins to True."""
    from bpp.models import Autor_Dyscyplina

    Autor_Dyscyplina.objects.create(
        autor=autor_jan_kowalski, dyscyplina_naukowa=dyscyplina1, rok=2023
    )

    wydawnictwo_ciagle.rok = 2023
    wydawnictwo_ciagle.save()
    wca = wydawnictwo_ciagle.dodaj_autora(
        autor_jan_kowalski, jednostka, dyscyplina_naukowa=dyscyplina1
    )
    wca.przypieta = False
    wca.save()

    with patch("ewaluacja_optymalizacja.tasks.reset_pins._wait_for_denorm"):
        with patch("ewaluacja_optymalizacja.tasks.reset_pins._run_bulk_optimization"):
            result = reset_all_pins_task.apply(args=(uczelnia.pk,)).result

    wca.refresh_from_db()
    assert wca.przypieta is True
    assert result["total_reset"] >= 1


# ============================================================================
# unpin_all_sensible_task tests
# ============================================================================


@pytest.mark.django_db
def test_unpin_all_sensible_task_no_opportunities(uczelnia):
    """Test unpin_all_sensible_task with no sensible opportunities."""
    result = unpin_all_sensible_task.apply(args=(uczelnia.pk,)).result

    assert result["uczelnia_id"] == uczelnia.pk
    assert result["total_opportunities"] == 0
    assert result["unpinned_count"] == 0
