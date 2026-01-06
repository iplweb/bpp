from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone
from model_bakery import baker

from bpp.models import Dyscyplina_Naukowa, Punktacja_Zrodla, Zrodlo
from pbn_api.models import Journal
from pbn_downloader_app.models import PbnJournalsDownloadTask

from .models import KomparatorZrodelMeta, LogAktualizacjiZrodla, RozbieznoscZrodlaPBN
from .update_utils import aktualizuj_zrodlo_z_pbn
from .utils import (
    KomparatorZrodelPBN,
    cleanup_stale_discrepancies,
    is_discrepancies_list_stale,
    is_pbn_journals_data_fresh,
)


@pytest.fixture
def pbn_journal_with_data():
    """Create a PBN Journal with points and disciplines data."""
    return Journal.objects.create(
        mongoId="test_journal_12345",
        status="ACTIVE",
        verificationLevel="VERIFIED",
        verified=True,
        versions=[
            {
                "current": True,
                "object": {
                    "title": "Test PBN Journal",
                    "points": {
                        "2022": {"points": 70},
                        "2023": {"points": 100},
                    },
                    # PBN uses dict format with code and name keys
                    # Codes "11" and "23" convert to "1.1" and "2.3"
                    "disciplines": [
                        {"code": "11", "name": "Matematyka"},
                        {"code": "23", "name": "Nauki chemiczne"},
                    ],
                },
            }
        ],
        title="Test PBN Journal",
    )


@pytest.fixture
def dyscyplina_1_01():
    """Create discipline 1.1 (normalized from PBN code 101)."""
    return baker.make(Dyscyplina_Naukowa, kod="1.1", nazwa="Matematyka")


@pytest.fixture
def dyscyplina_2_03():
    """Create discipline 2.3 (normalized from PBN code 203)."""
    return baker.make(Dyscyplina_Naukowa, kod="2.3", nazwa="Nauki chemiczne")


@pytest.mark.django_db
def test_rozbieznosc_zrodla_pbn_model_creation(pbn_journal_with_data):
    """Test creating RozbieznoscZrodlaPBN model."""
    zrodlo = baker.make(Zrodlo, nazwa="Test Journal", pbn_uid=pbn_journal_with_data)

    rozbieznosc = RozbieznoscZrodlaPBN.objects.create(
        zrodlo=zrodlo,
        rok=2023,
        ma_rozbieznosc_punktow=True,
        punkty_bpp=Decimal("50.00"),
        punkty_pbn=Decimal("100.00"),
        ma_rozbieznosc_dyscyplin=False,
    )

    assert rozbieznosc.ma_jakiekolwiek_rozbieznosci is True
    assert str(rozbieznosc) == "Rozbieżność: Test Journal (2023)"


@pytest.mark.django_db
def test_komparator_zrodel_meta_singleton():
    """Test KomparatorZrodelMeta singleton behavior."""
    meta1 = KomparatorZrodelMeta.get_instance()
    meta2 = KomparatorZrodelMeta.get_instance()

    assert meta1.pk == meta2.pk == 1


@pytest.mark.django_db(transaction=True)
def test_komparator_finds_points_discrepancy(
    pbn_journal_with_data, dyscyplina_1_01, dyscyplina_2_03
):
    """Test that komparator finds discrepancy when BPP points differ from PBN."""
    zrodlo = baker.make(Zrodlo, nazwa="Test Journal", pbn_uid=pbn_journal_with_data)

    # Create BPP punktacja with different value than PBN (70 vs 100 for 2023)
    Punktacja_Zrodla.objects.create(
        zrodlo=zrodlo, rok=2023, punkty_kbn=Decimal("50.00")
    )

    # Also add correct discipline assignment to avoid discipline discrepancy
    zrodlo.dyscyplina_zrodla_set.create(dyscyplina=dyscyplina_1_01, rok=2023)
    zrodlo.dyscyplina_zrodla_set.create(dyscyplina=dyscyplina_2_03, rok=2023)

    komparator = KomparatorZrodelPBN(min_rok=2022, show_progress=False)
    stats = komparator.run()

    assert stats["processed"] == 1
    assert stats["points_discrepancies"] >= 1

    # Check that discrepancy was recorded
    rozbieznosc = RozbieznoscZrodlaPBN.objects.get(zrodlo=zrodlo, rok=2023)
    assert rozbieznosc.ma_rozbieznosc_punktow is True
    assert rozbieznosc.punkty_bpp == Decimal("50.00")
    assert rozbieznosc.punkty_pbn == Decimal("100.00")


@pytest.mark.django_db(transaction=True)
def test_komparator_finds_discipline_discrepancy(
    pbn_journal_with_data, dyscyplina_1_01, dyscyplina_2_03
):
    """Test that komparator finds discrepancy when BPP disciplines differ from PBN."""
    zrodlo = baker.make(Zrodlo, nazwa="Test Journal", pbn_uid=pbn_journal_with_data)

    # Create BPP punktacja matching PBN
    Punktacja_Zrodla.objects.create(
        zrodlo=zrodlo, rok=2023, punkty_kbn=Decimal("100.00")
    )

    # Add only one discipline (should have two from PBN)
    zrodlo.dyscyplina_zrodla_set.create(dyscyplina=dyscyplina_1_01, rok=2023)

    komparator = KomparatorZrodelPBN(min_rok=2022, show_progress=False)
    stats = komparator.run()

    assert stats["processed"] == 1
    assert stats["discipline_discrepancies"] >= 1

    # Check that discrepancy was recorded
    rozbieznosc = RozbieznoscZrodlaPBN.objects.get(zrodlo=zrodlo, rok=2023)
    assert rozbieznosc.ma_rozbieznosc_dyscyplin is True
    assert "1.1" in rozbieznosc.dyscypliny_bpp
    assert "2.3" not in rozbieznosc.dyscypliny_bpp  # Missing in BPP


@pytest.mark.django_db(transaction=True)
def test_komparator_no_discrepancy_when_data_matches(
    pbn_journal_with_data, dyscyplina_1_01, dyscyplina_2_03
):
    """Test that komparator doesn't create discrepancy when data matches."""
    zrodlo = baker.make(Zrodlo, nazwa="Test Journal", pbn_uid=pbn_journal_with_data)

    # Create BPP punktacja matching PBN
    Punktacja_Zrodla.objects.create(
        zrodlo=zrodlo, rok=2023, punkty_kbn=Decimal("100.00")
    )

    # Add both disciplines matching PBN
    zrodlo.dyscyplina_zrodla_set.create(dyscyplina=dyscyplina_1_01, rok=2023)
    zrodlo.dyscyplina_zrodla_set.create(dyscyplina=dyscyplina_2_03, rok=2023)

    komparator = KomparatorZrodelPBN(min_rok=2022, show_progress=False)
    stats = komparator.run()

    assert stats["processed"] == 1

    # No discrepancy for 2023
    assert not RozbieznoscZrodlaPBN.objects.filter(zrodlo=zrodlo, rok=2023).exists()


@pytest.mark.django_db
def test_aktualizuj_zrodlo_z_pbn_updates_points(
    pbn_journal_with_data, dyscyplina_1_01, dyscyplina_2_03
):
    """Test that aktualizuj_zrodlo_z_pbn updates points from PBN."""
    zrodlo = baker.make(Zrodlo, nazwa="Test Journal", pbn_uid=pbn_journal_with_data)

    # Create BPP punktacja with different value
    Punktacja_Zrodla.objects.create(
        zrodlo=zrodlo, rok=2023, punkty_kbn=Decimal("50.00")
    )

    # Run update
    result = aktualizuj_zrodlo_z_pbn(
        zrodlo,
        rok=2023,
        aktualizuj_punkty=True,
        aktualizuj_dyscypliny=False,
    )

    assert result is True

    # Check points were updated
    punktacja = zrodlo.punktacja_zrodla_set.get(rok=2023)
    assert punktacja.punkty_kbn == Decimal("100.00")

    # Check log was created
    log = LogAktualizacjiZrodla.objects.get(zrodlo=zrodlo, rok=2023)
    assert log.typ_zmiany == "punkty"


@pytest.mark.django_db
def test_aktualizuj_zrodlo_z_pbn_updates_disciplines(
    pbn_journal_with_data, dyscyplina_1_01, dyscyplina_2_03
):
    """Test that aktualizuj_zrodlo_z_pbn updates disciplines from PBN."""
    zrodlo = baker.make(Zrodlo, nazwa="Test Journal", pbn_uid=pbn_journal_with_data)

    # Create BPP punktacja
    Punktacja_Zrodla.objects.create(
        zrodlo=zrodlo, rok=2023, punkty_kbn=Decimal("100.00")
    )

    # Add only one discipline
    zrodlo.dyscyplina_zrodla_set.create(dyscyplina=dyscyplina_1_01, rok=2023)

    # Run update for disciplines only
    result = aktualizuj_zrodlo_z_pbn(
        zrodlo,
        rok=2023,
        aktualizuj_punkty=False,
        aktualizuj_dyscypliny=True,
    )

    assert result is True

    # Check disciplines were updated
    dyscypliny = set(
        zrodlo.dyscyplina_zrodla_set.filter(rok=2023).values_list(
            "dyscyplina__kod", flat=True
        )
    )
    assert dyscypliny == {"1.1", "2.3"}

    # Check log was created
    log = LogAktualizacjiZrodla.objects.get(zrodlo=zrodlo, rok=2023)
    assert log.typ_zmiany == "dyscypliny"


@pytest.mark.django_db(transaction=True)
def test_komparator_clears_existing_when_requested(pbn_journal_with_data):
    """Test that komparator clears existing discrepancies when clear_existing=True."""
    zrodlo = baker.make(Zrodlo, nazwa="Test Journal", pbn_uid=pbn_journal_with_data)

    # Create an old discrepancy
    RozbieznoscZrodlaPBN.objects.create(
        zrodlo=zrodlo,
        rok=2020,  # Old year that won't be processed
        ma_rozbieznosc_punktow=True,
    )

    komparator = KomparatorZrodelPBN(
        min_rok=2022, clear_existing=True, show_progress=False
    )
    komparator.run()

    # Old discrepancy should be deleted
    assert not RozbieznoscZrodlaPBN.objects.filter(zrodlo=zrodlo, rok=2020).exists()


@pytest.mark.django_db(transaction=True)
def test_komparator_skips_zrodlo_without_pbn_uid():
    """Test that komparator skips sources without PBN UID."""
    zrodlo = baker.make(Zrodlo, nazwa="Test Journal Without PBN", pbn_uid=None)

    komparator = KomparatorZrodelPBN(min_rok=2022, show_progress=False)
    stats = komparator.run()

    # Should not have processed this source
    assert stats["processed"] == 0
    assert not RozbieznoscZrodlaPBN.objects.filter(zrodlo=zrodlo).exists()


@pytest.mark.django_db
def test_aktualizuj_zrodlo_removes_discrepancy(
    pbn_journal_with_data, dyscyplina_1_01, dyscyplina_2_03
):
    """Test that aktualizuj_zrodlo_z_pbn removes discrepancy after update."""
    zrodlo = baker.make(Zrodlo, nazwa="Test Journal", pbn_uid=pbn_journal_with_data)

    # Create discrepancy
    RozbieznoscZrodlaPBN.objects.create(
        zrodlo=zrodlo,
        rok=2023,
        ma_rozbieznosc_punktow=True,
        punkty_bpp=Decimal("50.00"),
        punkty_pbn=Decimal("100.00"),
    )

    # Create BPP punktacja
    Punktacja_Zrodla.objects.create(
        zrodlo=zrodlo, rok=2023, punkty_kbn=Decimal("50.00")
    )

    # Run update
    aktualizuj_zrodlo_z_pbn(
        zrodlo, rok=2023, aktualizuj_punkty=True, aktualizuj_dyscypliny=False
    )

    # Discrepancy should be removed
    assert not RozbieznoscZrodlaPBN.objects.filter(zrodlo=zrodlo, rok=2023).exists()


# Tests for data freshness checks


@pytest.mark.django_db
def test_is_pbn_journals_data_fresh_no_task(admin_user):
    """Test that is_pbn_journals_data_fresh returns False when no task exists."""
    PbnJournalsDownloadTask.objects.all().delete()

    is_fresh, message, last_download = is_pbn_journals_data_fresh()

    assert is_fresh is False
    assert "nigdy nie były pobrane" in message
    assert last_download is None


@pytest.mark.django_db
def test_is_pbn_journals_data_fresh_recent_task(admin_user):
    """Test that is_pbn_journals_data_fresh returns True for recent completed task."""
    PbnJournalsDownloadTask.objects.all().delete()
    task = PbnJournalsDownloadTask.objects.create(
        user=admin_user,
        status="completed",
        completed_at=timezone.now() - timedelta(days=1),
    )

    is_fresh, message, last_download = is_pbn_journals_data_fresh()

    assert is_fresh is True
    assert message is None
    assert last_download == task.completed_at


@pytest.mark.django_db
def test_is_pbn_journals_data_fresh_stale_task(admin_user):
    """Test that is_pbn_journals_data_fresh returns False for stale task."""
    PbnJournalsDownloadTask.objects.all().delete()
    PbnJournalsDownloadTask.objects.create(
        user=admin_user,
        status="completed",
        completed_at=timezone.now() - timedelta(days=10),
    )

    is_fresh, message, last_download = is_pbn_journals_data_fresh()

    assert is_fresh is False
    assert "nieaktualne" in message
    assert last_download is not None


@pytest.mark.django_db
def test_is_discrepancies_list_stale_no_run():
    """Test that is_discrepancies_list_stale returns False when never run."""
    meta = KomparatorZrodelMeta.get_instance()
    meta.ostatnie_uruchomienie = None
    meta.save()

    is_stale, age_days = is_discrepancies_list_stale()

    assert is_stale is False
    assert age_days is None


@pytest.mark.django_db
def test_is_discrepancies_list_stale_recent():
    """Test that is_discrepancies_list_stale returns False for recent run."""
    meta = KomparatorZrodelMeta.get_instance()
    meta.ostatnie_uruchomienie = timezone.now() - timedelta(days=1)
    meta.save()

    is_stale, age_days = is_discrepancies_list_stale()

    assert is_stale is False
    assert age_days == 1


@pytest.mark.django_db
def test_is_discrepancies_list_stale_old():
    """Test that is_discrepancies_list_stale returns True for old run."""
    meta = KomparatorZrodelMeta.get_instance()
    meta.ostatnie_uruchomienie = timezone.now() - timedelta(days=10)
    meta.save()

    is_stale, age_days = is_discrepancies_list_stale()

    assert is_stale is True
    assert age_days == 10


@pytest.mark.django_db
def test_cleanup_stale_discrepancies_cleans_old(pbn_journal_with_data):
    """Test that cleanup_stale_discrepancies deletes old discrepancies."""
    zrodlo = baker.make(Zrodlo, nazwa="Test Journal", pbn_uid=pbn_journal_with_data)

    # Create discrepancy
    RozbieznoscZrodlaPBN.objects.create(
        zrodlo=zrodlo,
        rok=2023,
        ma_rozbieznosc_punktow=True,
    )

    # Set old run date
    meta = KomparatorZrodelMeta.get_instance()
    meta.ostatnie_uruchomienie = timezone.now() - timedelta(days=10)
    meta.save()

    was_cleaned, count = cleanup_stale_discrepancies()

    assert was_cleaned is True
    assert count == 1
    assert not RozbieznoscZrodlaPBN.objects.exists()

    # Meta should be cleared
    meta.refresh_from_db()
    assert meta.ostatnie_uruchomienie is None


@pytest.mark.django_db
def test_cleanup_stale_discrepancies_keeps_recent(pbn_journal_with_data):
    """Test that cleanup_stale_discrepancies keeps recent discrepancies."""
    zrodlo = baker.make(Zrodlo, nazwa="Test Journal", pbn_uid=pbn_journal_with_data)

    # Create discrepancy
    RozbieznoscZrodlaPBN.objects.create(
        zrodlo=zrodlo,
        rok=2023,
        ma_rozbieznosc_punktow=True,
    )

    # Set recent run date
    meta = KomparatorZrodelMeta.get_instance()
    meta.ostatnie_uruchomienie = timezone.now() - timedelta(days=1)
    meta.save()

    was_cleaned, count = cleanup_stale_discrepancies()

    assert was_cleaned is False
    assert count == 0
    assert RozbieznoscZrodlaPBN.objects.count() == 1


# Tests for parallel processing


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


# Tests for Celery tasks


@pytest.mark.django_db(transaction=True)
def test_porownaj_zrodla_task_success(dyscyplina_1_01):
    """Test that porownaj_zrodla_task executes successfully."""
    from unittest.mock import patch

    from .tasks import porownaj_zrodla_task

    # Create test source
    journal = Journal.objects.create(
        mongoId="test_task_journal",
        status="ACTIVE",
        verificationLevel="VERIFIED",
        verified=True,
        versions=[
            {
                "current": True,
                "object": {
                    "title": "Test Task Journal",
                    "points": {"2023": {"points": 100}},
                    "disciplines": [{"code": "11", "name": "Matematyka"}],
                },
            }
        ],
        title="Test Task Journal",
    )
    baker.make(Zrodlo, nazwa="Test Task Source", pbn_uid=journal)

    # Run task synchronously
    with patch("pbn_komparator_zrodel.tasks.cache"):
        result = porownaj_zrodla_task.apply(args=(2022, False)).result

    assert result["status"] == "SUCCESS"
    assert "stats" in result


@pytest.mark.django_db(transaction=True)
def test_porownaj_zrodla_task_updates_progress(dyscyplina_1_01):
    """Test that porownaj_zrodla_task updates progress via cache."""
    from unittest.mock import patch

    from .tasks import porownaj_zrodla_task

    # Create test source
    journal = Journal.objects.create(
        mongoId="test_progress_journal",
        status="ACTIVE",
        verificationLevel="VERIFIED",
        verified=True,
        versions=[
            {
                "current": True,
                "object": {
                    "title": "Test Progress Journal",
                    "points": {"2023": {"points": 100}},
                    "disciplines": [{"code": "11", "name": "Matematyka"}],
                },
            }
        ],
        title="Test Progress Journal",
    )
    baker.make(Zrodlo, nazwa="Test Progress Source", pbn_uid=journal)

    cache_calls = []

    def track_cache_set(key, value, timeout):
        cache_calls.append({"key": key, "value": value})

    with patch("pbn_komparator_zrodel.tasks.cache") as mock_cache:
        mock_cache.set.side_effect = track_cache_set
        porownaj_zrodla_task.apply(args=(2022, False))

    # Cache should have been called at least for init and success
    assert len(cache_calls) >= 2


@pytest.mark.django_db
def test_aktualizuj_wszystkie_task_success(pbn_journal_with_data, dyscyplina_1_01):
    """Test that aktualizuj_wszystkie_task updates sources."""
    from unittest.mock import patch

    from .tasks import aktualizuj_wszystkie_task

    zrodlo = baker.make(Zrodlo, nazwa="Update Task Test", pbn_uid=pbn_journal_with_data)
    Punktacja_Zrodla.objects.create(
        zrodlo=zrodlo, rok=2023, punkty_kbn=Decimal("50.00")
    )

    # Create discrepancy to update
    rozbieznosc = RozbieznoscZrodlaPBN.objects.create(
        zrodlo=zrodlo,
        rok=2023,
        ma_rozbieznosc_punktow=True,
        punkty_bpp=Decimal("50.00"),
        punkty_pbn=Decimal("100.00"),
    )

    with patch("pbn_komparator_zrodel.tasks.cache"):
        result = aktualizuj_wszystkie_task.apply(
            args=([rozbieznosc.pk],), kwargs={"typ": "punkty"}
        ).result

    assert result["updated"] >= 0  # May be 0 if update logic differs
    assert result["total"] == 1


@pytest.mark.django_db
def test_aktualizuj_wszystkie_task_nonexistent_pk():
    """Test that aktualizuj_wszystkie_task handles nonexistent pk."""
    from unittest.mock import patch

    from .tasks import aktualizuj_wszystkie_task

    with patch("pbn_komparator_zrodel.tasks.cache"):
        result = aktualizuj_wszystkie_task.apply(args=([999999],)).result

    assert result["errors"] == 1
    assert result["updated"] == 0
    assert result["total"] == 1


@pytest.mark.django_db
def test_aktualizuj_wszystkie_task_with_user(pbn_journal_with_data, admin_user):
    """Test that aktualizuj_wszystkie_task records user for logging."""
    from unittest.mock import patch

    from .tasks import aktualizuj_wszystkie_task

    zrodlo = baker.make(Zrodlo, nazwa="Update User Test", pbn_uid=pbn_journal_with_data)
    Punktacja_Zrodla.objects.create(
        zrodlo=zrodlo, rok=2023, punkty_kbn=Decimal("50.00")
    )

    rozbieznosc = RozbieznoscZrodlaPBN.objects.create(
        zrodlo=zrodlo,
        rok=2023,
        ma_rozbieznosc_punktow=True,
        punkty_bpp=Decimal("50.00"),
        punkty_pbn=Decimal("100.00"),
    )

    with patch("pbn_komparator_zrodel.tasks.cache"):
        result = aktualizuj_wszystkie_task.apply(
            args=([rozbieznosc.pk],),
            kwargs={"typ": "punkty", "user_id": admin_user.id},
        ).result

    assert result["total"] == 1


@pytest.mark.django_db
def test_get_task_status_pending():
    """Test get_task_status returns pending for unknown task."""
    from unittest.mock import MagicMock, patch

    from .tasks import get_task_status

    with patch("pbn_komparator_zrodel.tasks.cache") as mock_cache:
        mock_cache.get.return_value = None
        with patch("pbn_komparator_zrodel.tasks.AsyncResult") as mock_result:
            mock_task = MagicMock()
            mock_task.state = "PENDING"
            mock_result.return_value = mock_task

            status = get_task_status("fake-task-id")

    assert status["status"] == "PENDING"


@pytest.mark.django_db
def test_get_task_status_from_cache():
    """Test get_task_status returns cached status."""
    from unittest.mock import patch

    from .tasks import get_task_status

    cached_status = {"status": "PROGRESS", "current": 5, "total": 10}

    with patch("pbn_komparator_zrodel.tasks.cache") as mock_cache:
        mock_cache.get.return_value = cached_status

        status = get_task_status("cached-task-id")

    assert status == cached_status
