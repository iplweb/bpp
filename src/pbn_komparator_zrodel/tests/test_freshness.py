"""Tests for data freshness checks and stale discrepancy cleanup."""

from datetime import timedelta

import pytest
from django.utils import timezone
from model_bakery import baker

from bpp.models import Zrodlo
from pbn_downloader_app.models import PbnJournalsDownloadTask

from ..models import KomparatorZrodelMeta, RozbieznoscZrodlaPBN
from ..utils import (
    cleanup_stale_discrepancies,
    is_discrepancies_list_stale,
    is_pbn_journals_data_fresh,
)


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
