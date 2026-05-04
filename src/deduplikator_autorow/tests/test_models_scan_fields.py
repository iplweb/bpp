"""Testy nowych pól: phase, scan_mode, PARTIAL_COMPLETED status."""

import pytest
from model_bakery import baker

from deduplikator_autorow.models import DuplicateCandidate, DuplicateScanRun


@pytest.mark.django_db
def test_scan_run_phase_field_default_blank():
    scan = DuplicateScanRun.objects.create()
    assert scan.phase == ""


@pytest.mark.django_db
def test_scan_run_phase_field_can_be_set():
    scan = DuplicateScanRun.objects.create(phase="general")
    scan.refresh_from_db()
    assert scan.phase == "general"


@pytest.mark.django_db
def test_scan_run_partial_completed_status():
    scan = DuplicateScanRun.objects.create(
        status=DuplicateScanRun.Status.PARTIAL_COMPLETED
    )
    scan.refresh_from_db()
    assert scan.status == "partial_completed"
    assert scan.get_status_display() == (
        "Częściowo zakończone (faza PBN OK, general anulowana)"
    )


@pytest.mark.django_db
def test_candidate_scan_mode_default_pbn():
    scan = DuplicateScanRun.objects.create()
    autor1 = baker.make("bpp.Autor")
    autor2 = baker.make("bpp.Autor")
    cand = DuplicateCandidate.objects.create(
        scan_run=scan,
        main_autor=autor1,
        duplicate_autor=autor2,
        confidence_score=80,
        confidence_percent=0.5,
        main_autor_name="Test Main",
        duplicate_autor_name="Test Dup",
    )
    cand.refresh_from_db()
    assert cand.scan_mode == "pbn"


@pytest.mark.django_db
def test_candidate_scan_mode_general():
    scan = DuplicateScanRun.objects.create()
    autor1 = baker.make("bpp.Autor")
    autor2 = baker.make("bpp.Autor")
    cand = DuplicateCandidate.objects.create(
        scan_run=scan,
        main_autor=autor1,
        duplicate_autor=autor2,
        confidence_score=80,
        confidence_percent=0.5,
        main_autor_name="Test Main",
        duplicate_autor_name="Test Dup",
        scan_mode="general",
    )
    cand.refresh_from_db()
    assert cand.scan_mode == "general"


@pytest.mark.django_db
def test_candidate_unique_constraint_includes_scan_mode():
    """Ta sama para (main, dup) może istnieć w obu trybach, ale nie dwa razy w jednym."""
    from django.db import IntegrityError, transaction

    scan = DuplicateScanRun.objects.create()
    autor1 = baker.make("bpp.Autor")
    autor2 = baker.make("bpp.Autor")

    DuplicateCandidate.objects.create(
        scan_run=scan,
        main_autor=autor1,
        duplicate_autor=autor2,
        confidence_score=80,
        confidence_percent=0.5,
        main_autor_name="A",
        duplicate_autor_name="B",
        scan_mode="pbn",
    )
    # Ta sama para w trybie general — OK
    DuplicateCandidate.objects.create(
        scan_run=scan,
        main_autor=autor1,
        duplicate_autor=autor2,
        confidence_score=80,
        confidence_percent=0.5,
        main_autor_name="A",
        duplicate_autor_name="B",
        scan_mode="general",
    )
    # Drugi raz w trybie pbn — IntegrityError
    with pytest.raises(IntegrityError):
        with transaction.atomic():
            DuplicateCandidate.objects.create(
                scan_run=scan,
                main_autor=autor1,
                duplicate_autor=autor2,
                confidence_score=80,
                confidence_percent=0.5,
                main_autor_name="A",
                duplicate_autor_name="B",
                scan_mode="pbn",
            )
