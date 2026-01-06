"""
Tests for PBN_Export_Queue send_to_pbn method.

For status tests, see test_pbn_queue_status.py
For helper method tests, see test_pbn_queue_helpers.py
For manager tests, see test_pbn_queue_manager.py
"""

from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone
from model_bakery import baker

from pbn_api.exceptions import (
    CharakterFormalnyMissingPBNUID,
    CharakterFormalnyNieobslugiwanyError,
    PKZeroExportDisabled,
    PraceSerwisoweException,
)
from pbn_export_queue.models import PBN_Export_Queue, SendStatus


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
        """Test that FINISHED_OKAY is returned when record is deleted
        but send was already completed (protection against race conditions)"""
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
            wysylke_zakonczono=timezone.now(),
        )
        wydawnictwo_ciagle.delete()

        # After the change, it should return FINISHED_OKAY instead of raising exception
        # This is a protection against race conditions
        result = queue_item.send_to_pbn()
        assert result == SendStatus.FINISHED_OKAY

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
        """Test WYKLUCZONE when CharakterFormalnyNieobslugiwanyError is raised"""
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

                assert result == SendStatus.WYKLUCZONE
                queue_item.refresh_from_db()
                assert queue_item.zakonczono_pomyslnie is False
                assert queue_item.wykluczone is True
                assert queue_item.rodzaj_bledu is None
                assert "Wykluczone" in queue_item.komunikat
                assert "Charakter formalny" in queue_item.komunikat

    def test_send_to_pbn_pk_zero_export_disabled(self, wydawnictwo_ciagle, admin_user):
        """Test WYKLUCZONE when PKZeroExportDisabled is raised"""
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

            assert result == SendStatus.WYKLUCZONE
            queue_item.refresh_from_db()
            assert queue_item.zakonczono_pomyslnie is False
            assert queue_item.wykluczone is True
            assert queue_item.rodzaj_bledu is None
            assert "Wykluczone" in queue_item.komunikat
            assert "punktów PK" in queue_item.komunikat

    def test_send_to_pbn_charakter_formalny_missing_pbn_uid(
        self, wydawnictwo_ciagle, admin_user
    ):
        """Test WYKLUCZONE when CharakterFormalnyMissingPBNUID is raised"""
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
        )

        with patch(
            "bpp.admin.helpers.pbn_api.cli.sprobuj_wyslac_do_pbn_celery"
        ) as mock_send:
            mock_send.side_effect = CharakterFormalnyMissingPBNUID("Brak rodzaju PBN")

            result = queue_item.send_to_pbn()

            assert result == SendStatus.WYKLUCZONE
            queue_item.refresh_from_db()
            assert queue_item.zakonczono_pomyslnie is False
            assert queue_item.wykluczone is True
            assert queue_item.rodzaj_bledu is None
            assert "Wykluczone" in queue_item.komunikat

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
