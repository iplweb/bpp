"""Tests for parallel processing in KomparatorZrodelPBN."""

from decimal import Decimal

import pytest
from model_bakery import baker

from bpp.models import Punktacja_Zrodla, Zrodlo
from pbn_api.models import Journal

from ..models import KomparatorZrodelMeta, RozbieznoscZrodlaPBN
from ..utils import KomparatorZrodelPBN


@pytest.mark.django_db(transaction=True)
def test_komparator_parallel_processing_multiple_sources(
    dyscyplina_1_01, dyscyplina_2_03
):
    """Test that parallel processing works correctly with multiple sources."""
    # Create multiple PBN journals and sources
    zrodla = []
    for i in range(5):
        journal = Journal.objects.create(
            mongoId=f"test_journal_parallel_{i}",
            status="ACTIVE",
            verificationLevel="VERIFIED",
            verified=True,
            versions=[
                {
                    "current": True,
                    "object": {
                        "title": f"Test PBN Journal {i}",
                        "points": {
                            "2023": {"points": 100 + i * 10},
                        },
                        "disciplines": [
                            {"code": "11", "name": "Matematyka"},
                        ],
                    },
                }
            ],
            title=f"Test PBN Journal {i}",
        )
        zrodlo = baker.make(Zrodlo, nazwa=f"Test Journal {i}", pbn_uid=journal)
        # Create punktacja with different value to trigger discrepancy
        Punktacja_Zrodla.objects.create(
            zrodlo=zrodlo, rok=2023, punkty_kbn=Decimal("50.00")
        )
        zrodla.append(zrodlo)

    komparator = KomparatorZrodelPBN(min_rok=2022, show_progress=False)
    stats = komparator.run()

    assert stats["processed"] == 5
    assert stats["points_discrepancies"] == 5
    assert RozbieznoscZrodlaPBN.objects.count() == 5


@pytest.mark.django_db(transaction=True)
def test_komparator_progress_callback_is_called(dyscyplina_1_01):
    """Test that progress callback is called during processing."""
    progress_calls = []

    def track_progress(current, total, stats):
        progress_calls.append(
            {"current": current, "total": total, "stats": dict(stats)}
        )

    # Create a source
    journal = Journal.objects.create(
        mongoId="test_callback",
        status="ACTIVE",
        verificationLevel="VERIFIED",
        verified=True,
        versions=[
            {
                "current": True,
                "object": {
                    "title": "Test Callback Journal",
                    "points": {"2023": {"points": 100}},
                    "disciplines": [{"code": "11", "name": "Matematyka"}],
                },
            }
        ],
        title="Test Callback Journal",
    )
    baker.make(Zrodlo, nazwa="Test Callback", pbn_uid=journal)

    komparator = KomparatorZrodelPBN(
        min_rok=2022, show_progress=False, progress_callback=track_progress
    )
    komparator.run()

    # Progress callback should have been called at least once
    assert len(progress_calls) >= 1
    # Final call should show 1 processed
    final_call = progress_calls[-1]
    assert final_call["current"] == 1
    assert final_call["total"] == 1


@pytest.mark.django_db
def test_komparator_thread_safe_stats():
    """Test that stats are thread-safe during parallel execution."""
    import threading

    komparator = KomparatorZrodelPBN(min_rok=2022, show_progress=False)

    # Simulate concurrent stat increments
    def increment_stats():
        for _ in range(100):
            komparator._increment_stat("processed")

    threads = [threading.Thread(target=increment_stats) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert komparator.stats["processed"] == 1000


@pytest.mark.django_db(transaction=True)
def test_komparator_handles_errors_gracefully(dyscyplina_1_01):
    """Test that komparator handles individual source errors without crashing."""
    # Create a valid source
    journal_valid = Journal.objects.create(
        mongoId="test_valid",
        status="ACTIVE",
        verificationLevel="VERIFIED",
        verified=True,
        versions=[
            {
                "current": True,
                "object": {
                    "title": "Valid Journal",
                    "points": {"2023": {"points": 100}},
                    "disciplines": [{"code": "11", "name": "Matematyka"}],
                },
            }
        ],
        title="Valid Journal",
    )
    baker.make(Zrodlo, nazwa="Valid Journal", pbn_uid=journal_valid)

    # Create a source with malformed data (no versions)
    journal_invalid = Journal.objects.create(
        mongoId="test_invalid",
        status="ACTIVE",
        verificationLevel="VERIFIED",
        verified=True,
        versions=[],  # Empty versions - will cause issues
        title="Invalid Journal",
    )
    baker.make(Zrodlo, nazwa="Invalid Journal", pbn_uid=journal_invalid)

    komparator = KomparatorZrodelPBN(min_rok=2022, show_progress=False)
    stats = komparator.run()

    # Should have processed both, with one possibly erroring or being skipped
    total_handled = (
        stats["processed"]
        + stats["skipped_no_data"]
        + stats["skipped_no_pbn"]
        + stats["errors"]
    )
    assert total_handled == 2


@pytest.mark.django_db(transaction=True)
def test_komparator_empty_sources():
    """Test that komparator handles case with no sources gracefully."""
    # Ensure no sources with pbn_uid
    Zrodlo.objects.all().delete()

    komparator = KomparatorZrodelPBN(min_rok=2022, show_progress=False)
    stats = komparator.run()

    assert stats["processed"] == 0
    assert stats["errors"] == 0

    # Meta should still be updated
    meta = KomparatorZrodelMeta.get_instance()
    assert meta.status == "completed"
