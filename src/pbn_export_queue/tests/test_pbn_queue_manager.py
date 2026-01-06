"""
Tests for PBN_Export_Queue manager methods and utilities.

For status tests, see test_pbn_queue_status.py
For send tests, see test_pbn_queue_send.py
For helper method tests, see test_pbn_queue_helpers.py
"""

from unittest.mock import MagicMock

import pytest
from django.utils import timezone
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle
from pbn_api.exceptions import AlreadyEnqueuedError
from pbn_export_queue.models import PBN_Export_Queue, model_table_exists


@pytest.mark.django_db
class TestManagerSprobuj_Utowrzyc_Wpis:
    """Tests for PBN_Export_QueueManager.sprobuj_utowrzyc_wpis method"""

    def test_sprobuj_utowrzyc_wpis_success(self, wydawnictwo_ciagle, admin_user):
        """Test successfully creating a queue entry"""
        result = PBN_Export_Queue.objects.sprobuj_utowrzyc_wpis(
            admin_user, wydawnictwo_ciagle
        )

        assert result.zamowil == admin_user
        assert result.rekord_do_wysylki == wydawnictwo_ciagle

    def test_sprobuj_utowrzyc_wpis_already_enqueued(
        self, wydawnictwo_ciagle, admin_user
    ):
        """Test that AlreadyEnqueuedError is raised when record is already enqueued"""
        baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
            wysylke_zakonczono=None,
        )

        with pytest.raises(AlreadyEnqueuedError):
            PBN_Export_Queue.objects.sprobuj_utowrzyc_wpis(
                admin_user, wydawnictwo_ciagle
            )

    def test_sprobuj_utowrzyc_wpis_allows_retry_after_completion(
        self, wydawnictwo_ciagle, admin_user
    ):
        """Test that new entry can be created if previous one is completed"""
        baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
            wysylke_zakonczono=timezone.now(),
        )

        result = PBN_Export_Queue.objects.sprobuj_utowrzyc_wpis(
            admin_user, wydawnictwo_ciagle
        )

        assert result.pk is not None


@pytest.mark.django_db
class TestManagerFilter_Rekord_Do_Wysylki:
    """Tests for PBN_Export_QueueManager.filter_rekord_do_wysylki method"""

    def test_filter_rekord_do_wysylki_finds_pending_record(
        self, wydawnictwo_ciagle, admin_user
    ):
        """Test that filter finds pending records"""
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
            wysylke_zakonczono=None,
        )

        result = PBN_Export_Queue.objects.filter_rekord_do_wysylki(wydawnictwo_ciagle)

        assert result.count() == 1
        assert result.first() == queue_item

    def test_filter_rekord_do_wysylki_excludes_finished_record(
        self, wydawnictwo_ciagle, admin_user
    ):
        """Test that filter excludes finished records"""
        baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
            wysylke_zakonczono=timezone.now(),
        )

        result = PBN_Export_Queue.objects.filter_rekord_do_wysylki(wydawnictwo_ciagle)

        assert result.count() == 0


@pytest.mark.django_db
def test_model_table_exists_true():
    """Test that model_table_exists returns True for existing table"""
    assert model_table_exists(Wydawnictwo_Ciagle) is True


@pytest.mark.django_db
def test_model_table_exists_false():
    """Test that model_table_exists returns False for non-existing table"""
    from django.db import connection

    # Create a mock model with a non-existent table name
    mock_model = MagicMock()
    mock_model._meta.db_table = "non_existent_table_xyz_123"

    # Check that the table doesn't exist
    assert "non_existent_table_xyz_123" not in connection.introspection.table_names()
    assert model_table_exists(mock_model) is False
