"""
Tests for PBN_Export_Queue status-related functionality.

For send tests, see test_pbn_queue_send.py
For helper method tests, see test_pbn_queue_helpers.py
For manager tests, see test_pbn_queue_manager.py
"""

from datetime import timedelta
from unittest.mock import patch

import pytest
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle
from pbn_export_queue.models import PBN_Export_Queue


@pytest.mark.django_db
class TestOstatnia_Aktualizacja:
    """Tests for ostatnia_aktualizacja property"""

    def test_ostatnia_aktualizacja_when_wysylke_zakonczono_is_set(
        self, wydawnictwo_ciagle, admin_user
    ):
        """Test that property returns wysylke_zakonczono when set"""
        now = timezone.now()
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
            zamowiono=now - timedelta(hours=3),
            wysylke_podjeto=now - timedelta(hours=2),
            wysylke_zakonczono=now,
        )
        assert queue_item.ostatnia_aktualizacja == now

    def test_ostatnia_aktualizacja_when_wysylke_podjeto_is_set(
        self, wydawnictwo_ciagle, admin_user
    ):
        """Test that property returns wysylke_podjeto when zakonczono is None"""
        now = timezone.now()
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
            zamowiono=now - timedelta(hours=2),
            wysylke_podjeto=now - timedelta(hours=1),
            wysylke_zakonczono=None,
        )
        assert queue_item.ostatnia_aktualizacja == now - timedelta(hours=1)

    def test_ostatnia_aktualizacja_when_only_zamowiono_is_set(
        self, wydawnictwo_ciagle, admin_user
    ):
        """Test that property returns zamowiono when others are None"""
        now = timezone.now()
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
            zamowiono=now,
            wysylke_podjeto=None,
            wysylke_zakonczono=None,
        )
        assert queue_item.ostatnia_aktualizacja == now


@pytest.mark.django_db
class TestCheckIfRecordStillExists:
    """Tests for check_if_record_still_exists method"""

    def test_check_if_record_still_exists_with_valid_record(
        self, wydawnictwo_ciagle, admin_user
    ):
        """Test that method returns True for existing record"""
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
        )
        assert queue_item.check_if_record_still_exists() is True

    def test_check_if_record_still_exists_when_no_content_type_id(self, admin_user):
        """Test that method returns False when content_type_id is missing"""
        queue_item = baker.make(PBN_Export_Queue, zamowil=admin_user)
        # Manually set content_type_id to None
        queue_item.content_type_id = None
        assert queue_item.check_if_record_still_exists() is False

    def test_check_if_record_still_exists_with_deleted_record(
        self, wydawnictwo_ciagle, admin_user
    ):
        """Test that method returns False when record is deleted"""
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
        )
        # Delete the record
        wydawnictwo_ciagle.delete()

        assert queue_item.check_if_record_still_exists() is False

    def test_check_if_record_still_exists_with_nonexistent_object_id(self, admin_user):
        """Test that method returns False when object_id doesn't exist"""
        queue_item = baker.make(
            PBN_Export_Queue,
            content_type=ContentType.objects.get_for_model(Wydawnictwo_Ciagle),
            object_id=999999,
            zamowil=admin_user,
        )
        assert queue_item.check_if_record_still_exists() is False

    @patch("pbn_export_queue.models.model_table_exists")
    def test_check_if_record_still_exists_when_table_does_not_exist(
        self, mock_table_exists, admin_user
    ):
        """Test that method returns False when table doesn't exist"""
        mock_table_exists.return_value = False

        queue_item = baker.make(
            PBN_Export_Queue,
            content_type=ContentType.objects.get_for_model(Wydawnictwo_Ciagle),
            object_id=1,
            zamowil=admin_user,
        )

        assert queue_item.check_if_record_still_exists() is False
