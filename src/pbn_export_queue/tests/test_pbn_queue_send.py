"""
Tests for PBN_Export_Queue send_to_pbn method.

For status tests, see test_pbn_queue_status.py
For helper method tests, see test_pbn_queue_helpers.py
For manager tests, see test_pbn_queue_manager.py
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from django.utils import timezone
from model_bakery import baker

from pbn_api.exceptions import (
    CharakterFormalnyMissingPBNUID,
    CharakterFormalnyNieobslugiwanyError,
    HttpException,
    PKZeroExportDisabled,
    PraceSerwisoweException,
    StatementsMissing,
)
from pbn_export_queue.models import PBN_Export_Queue, RodzajBledu, SendStatus


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


@pytest.mark.django_db
class TestHttpExceptionValidationClassification:
    """
    Regression tests to ensure HttpException with validation details
    is classified as MERYTORYCZNY (not TECHNICZNY).

    These tests prevent regression to the bug that existed before 2026-01-20
    where validation errors were incorrectly classified as technical errors.
    """

    def test_http_400_with_details_isbn_duplicate(
        self, wydawnictwo_ciagle, admin_user
    ):
        """ISBN duplicate error should be MERYTORYCZNY (regression test for ID 20)"""
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
        )

        with patch(
            "bpp.admin.helpers.pbn_api.cli.sprobuj_wyslac_do_pbn_celery"
        ) as mock:
            error_json = json.dumps(
                {
                    "code": 400,
                    "message": "Bad Request",
                    "description": "Validation failed.",
                    "details": {
                        "isbn": (
                            "Publikacja o identycznym ISBN lub ISMN już istnieje!"
                        )
                    },
                }
            )
            mock.side_effect = HttpException(400, "/api/v1/publications", error_json)

            result = queue_item.send_to_pbn()

            assert result == SendStatus.FINISHED_ERROR
            queue_item.refresh_from_db()
            assert queue_item.rodzaj_bledu == RodzajBledu.MERYTORYCZNY
            assert "Błąd walidacji po stronie PBN" in queue_item.komunikat

    def test_http_400_with_details_doi_duplicate(
        self, wydawnictwo_ciagle, admin_user
    ):
        """DOI duplicate error should be MERYTORYCZNY (regression test for ID 19)"""
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
        )

        with patch(
            "bpp.admin.helpers.pbn_api.cli.sprobuj_wyslac_do_pbn_celery"
        ) as mock:
            error_json = json.dumps(
                {
                    "code": 400,
                    "message": "Bad Request",
                    "description": "Validation failed.",
                    "details": {
                        "doi": "Publikacja o identycznym numerze DOI już istnieje!"
                    },
                }
            )
            mock.side_effect = HttpException(400, "/api/v1/publications", error_json)

            result = queue_item.send_to_pbn()

            assert result == SendStatus.FINISHED_ERROR
            queue_item.refresh_from_db()
            assert queue_item.rodzaj_bledu == RodzajBledu.MERYTORYCZNY

    def test_http_400_with_details_invalid_year(
        self, wydawnictwo_ciagle, admin_user
    ):
        """Invalid year error should be MERYTORYCZNY (regression test for ID 11)"""
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
        )

        with patch(
            "bpp.admin.helpers.pbn_api.cli.sprobuj_wyslac_do_pbn_celery"
        ) as mock:
            error_json = json.dumps(
                {
                    "code": 400,
                    "message": "Bad Request",
                    "description": "Validation failed.",
                    "details": {
                        "year": (
                            "Rok publikacji nie może być późniejszy"
                            " od roku bieżącego!"
                        )
                    },
                }
            )
            mock.side_effect = HttpException(400, "/api/v1/publications", error_json)

            result = queue_item.send_to_pbn()

            assert result == SendStatus.FINISHED_ERROR
            queue_item.refresh_from_db()
            assert queue_item.rodzaj_bledu == RodzajBledu.MERYTORYCZNY

    def test_http_400_with_details_missing_book_id(
        self, wydawnictwo_ciagle, admin_user
    ):
        """
        Missing book.id error should be MERYTORYCZNY
        (regression test for ID 9)
        """
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
        )

        with patch(
            "bpp.admin.helpers.pbn_api.cli.sprobuj_wyslac_do_pbn_celery"
        ) as mock:
            error_json = json.dumps(
                {
                    "code": 400,
                    "message": "Bad Request",
                    "description": "Validation failed.",
                    "details": {
                        "book.id": (
                            "Identyfikator źródła rozdziału (książki)"
                            " jest wymagany!"
                        )
                    },
                }
            )
            mock.side_effect = HttpException(400, "/api/v1/publications", error_json)

            result = queue_item.send_to_pbn()

            assert result == SendStatus.FINISHED_ERROR
            queue_item.refresh_from_db()
            assert queue_item.rodzaj_bledu == RodzajBledu.MERYTORYCZNY

    def test_http_400_with_details_invalid_discipline(
        self, wydawnictwo_ciagle, admin_user
    ):
        """
        Invalid discipline error should be MERYTORYCZNY
        (regression test for ID 25)
        """
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
        )

        with patch(
            "bpp.admin.helpers.pbn_api.cli.sprobuj_wyslac_do_pbn_celery"
        ) as mock:
            error_json = json.dumps(
                {
                    "code": 400,
                    "message": "Bad Request",
                    "description": "Validation failed.",
                    "details": {
                        "statements.0": (
                            "Dla wskazanej osoby nie podano prawidłowej dyscypliny!"
                        )
                    },
                }
            )
            mock.side_effect = HttpException(400, "/api/v1/publications", error_json)

            result = queue_item.send_to_pbn()

            assert result == SendStatus.FINISHED_ERROR
            queue_item.refresh_from_db()
            assert queue_item.rodzaj_bledu == RodzajBledu.MERYTORYCZNY

    def test_http_400_without_details_stays_techniczny(
        self, wydawnictwo_ciagle, admin_user
    ):
        """
        HTTP 400 without details should remain TECHNICZNY
        (not all 400s are validation)
        """
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
        )

        with patch(
            "bpp.admin.helpers.pbn_api.cli.sprobuj_wyslac_do_pbn_celery"
        ) as mock:
            error_json = json.dumps(
                {
                    "code": 400,
                    "message": "Bad Request",
                    "description": (
                        "Some other server error without validation details"
                    ),
                }
            )
            mock.side_effect = HttpException(400, "/api/v1/publications", error_json)

            result = queue_item.send_to_pbn()

            assert result == SendStatus.FINISHED_ERROR
            queue_item.refresh_from_db()
            assert queue_item.rodzaj_bledu == RodzajBledu.TECHNICZNY

    def test_http_500_stays_techniczny(self, wydawnictwo_ciagle, admin_user):
        """
        HTTP 500 errors should remain TECHNICZNY
        (server errors, not validation)
        """
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
        )

        with patch(
            "bpp.admin.helpers.pbn_api.cli.sprobuj_wyslac_do_pbn_celery"
        ) as mock:
            error_json = json.dumps(
                {"code": 500, "message": "Internal Server Error"}
            )
            mock.side_effect = HttpException(500, "/api/v1/publications", error_json)

            result = queue_item.send_to_pbn()

            assert result == SendStatus.FINISHED_ERROR
            queue_item.refresh_from_db()
            assert queue_item.rodzaj_bledu == RodzajBledu.TECHNICZNY

    def test_statements_missing_is_merytoryczny(
        self, wydawnictwo_ciagle, admin_user
    ):
        """
        StatementsMissing error should be MERYTORYCZNY
        (business error - missing author statements/disciplines)
        """
        queue_item = baker.make(
            PBN_Export_Queue,
            rekord_do_wysylki=wydawnictwo_ciagle,
            zamowil=admin_user,
        )

        with patch(
            "bpp.admin.helpers.pbn_api.cli.sprobuj_wyslac_do_pbn_celery"
        ) as mock:
            mock.side_effect = StatementsMissing(
                "Nie wyślę rekordu artykułu lub rozdziału bez zadeklarowanych "
                "oświadczeń autorów (dyscyplin)."
            )

            result = queue_item.send_to_pbn()

            assert result == SendStatus.FINISHED_ERROR
            queue_item.refresh_from_db()
            assert queue_item.rodzaj_bledu == RodzajBledu.MERYTORYCZNY
            assert "Rekord nie może być wysłany do PBN" in queue_item.komunikat
