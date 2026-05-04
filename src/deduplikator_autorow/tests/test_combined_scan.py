"""Testy combined task scan_for_duplicates (PBN + general)."""

from unittest import mock

import pytest
from model_bakery import baker

from deduplikator_autorow.models import DuplicateCandidate, DuplicateScanRun
from deduplikator_autorow.tasks import scan_for_duplicates


@pytest.mark.django_db
def test_combined_scan_runs_both_phases_status_completed():
    """Sukces obu faz → status COMPLETED."""
    result = scan_for_duplicates.apply().result
    assert result["status"] == "success"
    scan = DuplicateScanRun.objects.get(pk=result["scan_run_id"])
    assert scan.status == DuplicateScanRun.Status.COMPLETED


@pytest.mark.django_db
def test_combined_scan_general_finds_duplicates():
    """Faza general dodaje DuplicateCandidate(scan_mode='general')."""
    baker.make("bpp.Autor", nazwisko="Hawkins", imiona="Lee")
    baker.make("bpp.Autor", nazwisko="Hawkins", imiona="Lee")
    result = scan_for_duplicates.apply().result
    scan = DuplicateScanRun.objects.get(pk=result["scan_run_id"])
    assert (
        DuplicateCandidate.objects.filter(scan_run=scan, scan_mode="general").count()
        >= 1
    )


@pytest.mark.django_db
def test_cancel_during_general_phase_leaves_partial_completed():
    """Anulowanie w fazie 2 (general) → PARTIAL_COMPLETED."""
    baker.make("bpp.Autor", nazwisko="Igor", imiona="Test")
    baker.make("bpp.Autor", nazwisko="Igor", imiona="Test")

    def fake_general(scan_run, *args, **kwargs):
        scan_run.status = DuplicateScanRun.Status.CANCELLED
        scan_run.save(update_fields=["status"])

    with mock.patch(
        "deduplikator_autorow.tasks._run_general_phase",
        side_effect=fake_general,
    ):
        result = scan_for_duplicates.apply().result

    scan = DuplicateScanRun.objects.get(pk=result["scan_run_id"])
    assert scan.status == DuplicateScanRun.Status.PARTIAL_COMPLETED
    assert result["status"] == "partial_completed"


@pytest.mark.django_db
def test_cancel_during_pbn_phase_leaves_cancelled():
    """Anulowanie w fazie 1 (PBN) → CANCELLED, faza 2 nie startuje."""

    def fake_pbn(scan_run, *args, **kwargs):
        scan_run.status = DuplicateScanRun.Status.CANCELLED
        scan_run.save(update_fields=["status"])

    with (
        mock.patch(
            "deduplikator_autorow.tasks._run_pbn_phase",
            side_effect=fake_pbn,
        ),
        mock.patch("deduplikator_autorow.tasks._run_general_phase") as general_mock,
    ):
        result = scan_for_duplicates.apply().result
        general_mock.assert_not_called()

    scan = DuplicateScanRun.objects.get(pk=result["scan_run_id"])
    assert scan.status == DuplicateScanRun.Status.CANCELLED
    assert result["status"] == "cancelled"


@pytest.mark.django_db
def test_phase_field_set_during_run():
    """Pole `phase` ustawione na 'pbn' przy fazie 1, 'general' przy fazie 2."""
    phases_seen = []

    from deduplikator_autorow import tasks as deduptasks

    original_pbn = deduptasks._run_pbn_phase
    original_general = deduptasks._run_general_phase

    def spy_pbn(scan_run, *a, **kw):
        scan_run.refresh_from_db()
        phases_seen.append(("pbn", scan_run.phase))
        return original_pbn(scan_run, *a, **kw)

    def spy_general(scan_run, *a, **kw):
        scan_run.refresh_from_db()
        phases_seen.append(("general", scan_run.phase))
        return original_general(scan_run, *a, **kw)

    with (
        mock.patch.object(deduptasks, "_run_pbn_phase", spy_pbn),
        mock.patch.object(deduptasks, "_run_general_phase", spy_general),
    ):
        scan_for_duplicates.apply()

    assert phases_seen == [("pbn", "pbn"), ("general", "general")]
