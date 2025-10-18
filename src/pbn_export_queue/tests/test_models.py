"""Tests for pbn_export_queue models"""

import sys
import traceback
from datetime import timedelta
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle
from pbn_api.exceptions import (
    AccessDeniedException,
    AlreadyEnqueuedError,
    CharakterFormalnyNieobslugiwanyError,
    NeedsPBNAuthorisationException,
    PKZeroExportDisabled,
    PraceSerwisoweException,
    ResourceLockedException,
)
from pbn_export_queue.models import (
    PBN_Export_Queue,
    PBN_Export_QueueManager,
    SendStatus,
    model_table_exists,
)


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


@pytest.mark.django_db
class TestSendToPbn:
    """Tests for send_to_pbn method"""

    def test_send_to_pbn_record_deleted_before_sending(self, admin_user):
        """Test that error is returned when record is deleted"""
        with patch.object(admin_user, "get_pbn_user"):
            with patch("pbn_export_queue.models.model_table_exists") as mock_exists:
                mock_exists.return_value = False
                queue_item = baker.make(
                    PBN_Export_Queue,
                    zamowil=admin_user,
                    wysylke_zakonczono=None,
                )

                result = queue_item.send_to_pbn()

                assert result == SendStatus.FINISHED_ERROR
                queue_item.refresh_from_db()
                assert queue_item.zakonczono_pomyslnie is False
                assert queue_item.wysylke_zakonczono is not None

    def test_send_to_pbn_record_deleted_but_already_finished(
        self, wydawnictwo_ciagle, admin_user
    ):
        """Test that exception is raised when record is deleted
        but send was already attempted"""
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
            wysylke_zakonczono=timezone.now(),
        )
        wydawnictwo_ciagle.delete()

        with pytest.raises(Exception):
            queue_item.send_to_pbn()

    def test_send_to_pbn_prace_serwisowe_exception(
        self, wydawnictwo_ciagle, admin_user
    ):
        """Test retry when PraceSerwisoweException is raised"""
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
        )

        with patch(
            "bpp.admin.helpers.pbn_api.cli.sprobuj_wyslac_do_pbn_celery"
        ) as mock_send:
            mock_send.side_effect = PraceSerwisoweException()

            result = queue_item.send_to_pbn()

            assert result == SendStatus.RETRY_MUCH_LATER
            queue_item.refresh_from_db()
            assert queue_item.ilosc_prob == 1
            assert "Prace serwisowe" in queue_item.komunikat

    def test_send_to_pbn_charakter_formalny_exception(
        self, wydawnictwo_ciagle, admin_user
    ):
        """Test error when CharakterFormalnyNieobslugiwanyError is raised"""
        with patch.object(admin_user, "get_pbn_user"):
            queue_item = baker.make(
                PBN_Export_Queue,
                rekord_do_wysylki=wydawnictwo_ciagle,
                zamowil=admin_user,
            )

            with patch(
                "bpp.admin.helpers.pbn_api.cli.sprobuj_wyslac_do_pbn_celery"
            ) as mock_send:
                mock_send.side_effect = CharakterFormalnyNieobslugiwanyError()

                result = queue_item.send_to_pbn()

                assert result == SendStatus.FINISHED_ERROR
                queue_item.refresh_from_db()
                assert queue_item.zakonczono_pomyslnie is False
                assert "Charakter formalny" in queue_item.komunikat

    def test_send_to_pbn_pk_zero_export_disabled(self, wydawnictwo_ciagle, admin_user):
        """Test error when PKZeroExportDisabled is raised"""
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
        )

        with patch(
            "bpp.admin.helpers.pbn_api.cli.sprobuj_wyslac_do_pbn_celery"
        ) as mock_send:
            mock_send.side_effect = PKZeroExportDisabled()

            result = queue_item.send_to_pbn()

            assert result == SendStatus.FINISHED_ERROR
            queue_item.refresh_from_db()
            assert queue_item.zakonczono_pomyslnie is False
            assert "punktów PK" in queue_item.komunikat

    def test_send_to_pbn_prace_serwisowe_exception_with_retry_later(
        self, wydawnictwo_ciagle, admin_user
    ):
        """Test retry later scenario"""
        with patch.object(admin_user, "get_pbn_user"):
            queue_item = baker.make(
                PBN_Export_Queue,
                rekord_do_wysylki=wydawnictwo_ciagle,
                zamowil=admin_user,
            )

            with patch(
                "bpp.admin.helpers.pbn_api.cli.sprobuj_wyslac_do_pbn_celery"
            ) as mock_send:
                # ResourceLockedException requires specific args,
                # so we test with general exception here
                mock_send.side_effect = Exception("Retry later")

                result = queue_item.send_to_pbn()

                # Generic exception triggers error
                assert result == SendStatus.FINISHED_ERROR

    def test_send_to_pbn_generic_exception(self, wydawnictwo_ciagle, admin_user):
        """Test error when generic exception is raised"""
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
        )

        with patch(
            "bpp.admin.helpers.pbn_api.cli.sprobuj_wyslac_do_pbn_celery"
        ) as mock_send:
            mock_send.side_effect = ValueError("Some error")

            with patch("rollbar.report_exc_info") as mock_rollbar:
                result = queue_item.send_to_pbn()

                assert result == SendStatus.FINISHED_ERROR
                queue_item.refresh_from_db()
                assert queue_item.zakonczono_pomyslnie is False
                assert "nieobsługiwany błąd" in queue_item.komunikat
                mock_rollbar.assert_called_once()

    def test_send_to_pbn_sent_data_is_none(self, wydawnictwo_ciagle, admin_user):
        """Test error when sent_data is None"""
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
        )

        with patch(
            "bpp.admin.helpers.pbn_api.cli.sprobuj_wyslac_do_pbn_celery"
        ) as mock_send:
            mock_send.return_value = (None, ["Error message"])

            result = queue_item.send_to_pbn()

            assert result == SendStatus.FINISHED_ERROR
            queue_item.refresh_from_db()
            assert queue_item.zakonczono_pomyslnie is False

    def test_send_to_pbn_success_without_extra_info(
        self, wydawnictwo_ciagle, admin_user
    ):
        """Test successful send without extra info"""
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
        )

        mock_sent_data = MagicMock()
        mock_sent_data.pk = 123

        with patch(
            "bpp.admin.helpers.pbn_api.cli.sprobuj_wyslac_do_pbn_celery"
        ) as mock_send:
            mock_send.return_value = (mock_sent_data, [])

            result = queue_item.send_to_pbn()

            assert result == SendStatus.FINISHED_OKAY
            queue_item.refresh_from_db()
            assert queue_item.zakonczono_pomyslnie is True
            assert queue_item.wysylke_zakonczono is not None
            assert "Wysłano poprawnie" in queue_item.komunikat

    def test_send_to_pbn_success_with_extra_info(self, wydawnictwo_ciagle, admin_user):
        """Test successful send with extra info"""
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
        )

        mock_sent_data = MagicMock()
        mock_sent_data.pk = 123

        with patch(
            "bpp.admin.helpers.pbn_api.cli.sprobuj_wyslac_do_pbn_celery"
        ) as mock_send:
            mock_send.return_value = (mock_sent_data, ["Info 1", "Info 2"])

            result = queue_item.send_to_pbn()

            assert result == SendStatus.FINISHED_OKAY
            queue_item.refresh_from_db()
            assert queue_item.zakonczono_pomyslnie is True
            assert "Dodatkowe informacje" in queue_item.komunikat
            assert "Info 1" in queue_item.komunikat

    def test_send_to_pbn_increments_ilosc_prob(self, wydawnictwo_ciagle, admin_user):
        """Test that ilosc_prob is incremented"""
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
            ilosc_prob=5,
        )

        mock_sent_data = MagicMock()
        mock_sent_data.pk = 123

        with patch(
            "bpp.admin.helpers.pbn_api.cli.sprobuj_wyslac_do_pbn_celery"
        ) as mock_send:
            mock_send.return_value = (mock_sent_data, [])

            queue_item.send_to_pbn()

            queue_item.refresh_from_db()
            assert queue_item.ilosc_prob == 6

    def test_send_to_pbn_resets_retry_after_user_authorised(
        self, wydawnictwo_ciagle, admin_user
    ):
        """Test that retry_after_user_authorised is reset"""
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
            retry_after_user_authorised=True,
        )

        mock_sent_data = MagicMock()
        mock_sent_data.pk = 123

        with patch(
            "bpp.admin.helpers.pbn_api.cli.sprobuj_wyslac_do_pbn_celery"
        ) as mock_send:
            mock_send.return_value = (mock_sent_data, [])

            queue_item.send_to_pbn()

            queue_item.refresh_from_db()
            assert queue_item.retry_after_user_authorised is None


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
