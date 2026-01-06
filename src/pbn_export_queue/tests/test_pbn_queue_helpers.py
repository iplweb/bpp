"""
Tests for PBN_Export_Queue helper methods.

For status tests, see test_pbn_queue_status.py
For send tests, see test_pbn_queue_send.py
For manager tests, see test_pbn_queue_manager.py
"""

import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from model_bakery import baker

from pbn_export_queue.models import PBN_Export_Queue, SendStatus


@pytest.mark.django_db
class TestPrepareForResend:
    """Tests for prepare_for_resend method"""

    def test_prepare_for_resend_without_user(self, wydawnictwo_ciagle, admin_user):
        """Test prepare_for_resend without user parameter"""
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
            wysylke_zakonczono=timezone.now(),
            zakonczono_pomyslnie=True,
            retry_after_user_authorised=True,
        )

        queue_item.prepare_for_resend()

        queue_item.refresh_from_db()
        assert queue_item.wysylke_zakonczono is None
        assert queue_item.zakonczono_pomyslnie is None
        assert queue_item.retry_after_user_authorised is None
        assert "Ponownie wysłano" in queue_item.komunikat

    def test_prepare_for_resend_with_user(self, wydawnictwo_ciagle, admin_user):
        """Test prepare_for_resend with user parameter"""
        User = get_user_model()
        other_user = baker.make(User, username="other_test_user")
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
            wysylke_zakonczono=timezone.now(),
        )

        queue_item.prepare_for_resend(user=other_user)

        queue_item.refresh_from_db()
        assert queue_item.zamowil == other_user
        assert "other_test_user" in queue_item.komunikat

    def test_prepare_for_resend_with_message_suffix(
        self, wydawnictwo_ciagle, admin_user
    ):
        """Test prepare_for_resend with message_suffix"""
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
            wysylke_zakonczono=timezone.now(),
        )

        queue_item.prepare_for_resend(message_suffix=" test suffix")

        queue_item.refresh_from_db()
        assert "test suffix" in queue_item.komunikat


@pytest.mark.django_db
class TestDopisz_Komunikat:
    """Tests for dopisz_komunikat method"""

    def test_dopisz_komunikat_to_empty_field(self, wydawnictwo_ciagle, admin_user):
        """Test adding message to empty komunikat field"""
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
            komunikat=None,
        )

        queue_item.dopisz_komunikat("Test message")

        assert "Test message" in queue_item.komunikat
        assert "=" in queue_item.komunikat

    def test_dopisz_komunikat_to_existing_field(self, wydawnictwo_ciagle, admin_user):
        """Test adding message to existing komunikat field"""
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
            komunikat="Old message",
        )

        queue_item.dopisz_komunikat("New message")

        assert "New message" in queue_item.komunikat
        assert "Old message" in queue_item.komunikat


@pytest.mark.django_db
class TestError:
    """Tests for error method"""

    def test_error_sets_fields_correctly(self, wydawnictwo_ciagle, admin_user):
        """Test that error method sets fields correctly"""
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
        )

        result = queue_item.error("Test error")

        assert result == SendStatus.FINISHED_ERROR
        queue_item.refresh_from_db()
        assert queue_item.wysylke_zakonczono is not None
        assert queue_item.zakonczono_pomyslnie is False
        assert "Test error" in queue_item.komunikat


@pytest.mark.django_db
class TestExclude:
    """Tests for exclude method"""

    def test_exclude_sets_fields_correctly(self, wydawnictwo_ciagle, admin_user):
        """Test that exclude method sets fields correctly"""
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
        )

        result = queue_item.exclude("Test exclusion message")

        assert result == SendStatus.WYKLUCZONE
        queue_item.refresh_from_db()
        assert queue_item.wysylke_zakonczono is not None
        assert queue_item.zakonczono_pomyslnie is False
        assert queue_item.wykluczone is True
        assert queue_item.rodzaj_bledu is None
        assert "Test exclusion message" in queue_item.komunikat

    def test_exclude_differs_from_error(self, wydawnictwo_ciagle, admin_user):
        """Test that exclude differs from error in key fields"""
        queue_item1 = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
        )
        queue_item2 = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
        )

        queue_item1.exclude("Exclusion")
        queue_item2.error("Error", rodzaj="MERYT")

        queue_item1.refresh_from_db()
        queue_item2.refresh_from_db()

        # Both have zakonczono_pomyslnie=False
        assert queue_item1.zakonczono_pomyslnie is False
        assert queue_item2.zakonczono_pomyslnie is False

        # But exclude sets wykluczone=True and rodzaj_bledu=None
        assert queue_item1.wykluczone is True
        assert queue_item1.rodzaj_bledu is None

        # While error keeps wykluczone=False and sets rodzaj_bledu
        assert queue_item2.wykluczone is False
        assert queue_item2.rodzaj_bledu == "MERYT"


@pytest.mark.django_db
class TestPrepareForResendResetsWykluczone:
    """Tests for prepare_for_resend resetting wykluczone"""

    def test_prepare_for_resend_resets_wykluczone(self, wydawnictwo_ciagle, admin_user):
        """Test that prepare_for_resend resets wykluczone field"""
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
            wykluczone=True,
            wysylke_zakonczono=timezone.now(),
            zakonczono_pomyslnie=False,
        )

        queue_item.prepare_for_resend()

        queue_item.refresh_from_db()
        assert queue_item.wykluczone is False
        assert queue_item.wysylke_zakonczono is None
        assert queue_item.zakonczono_pomyslnie is None
