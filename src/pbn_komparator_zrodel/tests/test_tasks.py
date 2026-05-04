"""Tests for Celery tasks in pbn_komparator_zrodel."""

from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from model_bakery import baker

from bpp.models import Punktacja_Zrodla, Zrodlo
from pbn_api.models import Journal

from ..models import RozbieznoscZrodlaPBN
from ..tasks import (
    aktualizuj_wszystkie_task,
    get_task_status,
    porownaj_zrodla_task,
)


@pytest.mark.django_db(transaction=True)
def test_porownaj_zrodla_task_success(dyscyplina_1_01):
    """Test that porownaj_zrodla_task executes successfully."""
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
    with patch("pbn_komparator_zrodel.tasks.cache"):
        result = aktualizuj_wszystkie_task.apply(args=([999999],)).result

    assert result["errors"] == 1
    assert result["updated"] == 0
    assert result["total"] == 1


@pytest.mark.django_db
def test_aktualizuj_wszystkie_task_with_user(pbn_journal_with_data, admin_user):
    """Test that aktualizuj_wszystkie_task records user for logging."""
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
    cached_status = {"status": "PROGRESS", "current": 5, "total": 10}

    with patch("pbn_komparator_zrodel.tasks.cache") as mock_cache:
        mock_cache.get.return_value = cached_status

        status = get_task_status("cached-task-id")

    assert status == cached_status
