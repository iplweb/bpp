"""
Tests for pbn_integrator.utils.mongodb_ops module.

Tests cover:
- zapisz_publikacje_instytucji error handling (HttpException 500)
- zapisz_oswiadczenie_instytucji error handling (HttpException 500)
- Verification that logger and rollbar are called on errors
"""

from unittest.mock import MagicMock, patch

import pytest

from pbn_api.exceptions import HttpException

# ============================================================================
# UNIT TESTS - zapisz_publikacje_instytucji
# ============================================================================


class TestZapiszPublikacjeInstytucji:
    """Test zapisz_publikacje_instytucji function error handling"""

    @pytest.fixture
    def sample_elem(self):
        """Sample element data for testing"""
        return {
            "publicationId": "pub123",
            "institutionId": "inst456",
            "insPersonId": "person789",
            "publicationVersion": 1,
            "publicationYear": 2024,
            "publicationType": "ARTICLE",
            "userType": "AUTHOR",
            "snapshot": None,
        }

    @pytest.fixture
    def mock_client(self):
        """Mock PBN client"""
        return MagicMock()

    def test_logs_and_reports_on_publication_http_500(self, sample_elem, mock_client):
        """Should log warning and report to rollbar when publication fetch fails"""
        from pbn_integrator.utils.mongodb_ops import zapisz_publikacje_instytucji

        http_exc = HttpException(500, "http://test.url", "Internal Server Error")

        with (
            patch(
                "pbn_integrator.utils.mongodb_ops.ensure_publication_exists",
                side_effect=http_exc,
            ),
            patch("pbn_integrator.utils.mongodb_ops.logger") as mock_logger,
            patch("pbn_integrator.utils.mongodb_ops.rollbar") as mock_rollbar,
        ):
            result = zapisz_publikacje_instytucji(sample_elem, None, client=mock_client)

            # Should return early (None)
            assert result is None

            # Should log warning
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert "publikacji" in call_args[0][0]
            assert sample_elem["publicationId"] in call_args[0]

            # Should report to rollbar
            mock_rollbar.report_exc_info.assert_called_once()

    def test_logs_and_reports_on_institution_http_500(self, sample_elem, mock_client):
        """Should log warning and report to rollbar when institution fetch fails"""
        from pbn_integrator.utils.mongodb_ops import zapisz_publikacje_instytucji

        http_exc = HttpException(500, "http://test.url", "Internal Server Error")

        with (
            patch("pbn_integrator.utils.mongodb_ops.ensure_publication_exists"),
            patch(
                "pbn_integrator.utils.mongodb_ops.ensure_institution_exists",
                side_effect=http_exc,
            ),
            patch("pbn_integrator.utils.mongodb_ops.logger") as mock_logger,
            patch("pbn_integrator.utils.mongodb_ops.rollbar") as mock_rollbar,
        ):
            result = zapisz_publikacje_instytucji(sample_elem, None, client=mock_client)

            # Should return early (None)
            assert result is None

            # Should log warning
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert "instytucji" in call_args[0][0]
            assert sample_elem["institutionId"] in call_args[0]

            # Should report to rollbar
            mock_rollbar.report_exc_info.assert_called_once()

    def test_logs_and_reports_on_person_http_500(self, sample_elem, mock_client):
        """Should log warning and report to rollbar when person fetch fails"""
        from pbn_integrator.utils.mongodb_ops import zapisz_publikacje_instytucji

        http_exc = HttpException(500, "http://test.url", "Internal Server Error")

        with (
            patch("pbn_integrator.utils.mongodb_ops.ensure_publication_exists"),
            patch("pbn_integrator.utils.mongodb_ops.ensure_institution_exists"),
            patch(
                "pbn_integrator.utils.mongodb_ops.ensure_person_exists",
                side_effect=http_exc,
            ),
            patch("pbn_integrator.utils.mongodb_ops.logger") as mock_logger,
            patch("pbn_integrator.utils.mongodb_ops.rollbar") as mock_rollbar,
        ):
            result = zapisz_publikacje_instytucji(sample_elem, None, client=mock_client)

            # Should return early (None)
            assert result is None

            # Should log warning
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert "osoby" in call_args[0][0]
            assert sample_elem["insPersonId"] in call_args[0]

            # Should report to rollbar
            mock_rollbar.report_exc_info.assert_called_once()

    def test_does_not_log_on_non_500_http_error(self, sample_elem, mock_client):
        """Should not log or report for non-500 HTTP errors (re-raises)"""
        from pbn_integrator.utils.mongodb_ops import zapisz_publikacje_instytucji

        http_exc = HttpException(404, "http://test.url", "Not Found")

        with (
            patch(
                "pbn_integrator.utils.mongodb_ops.ensure_publication_exists",
                side_effect=http_exc,
            ),
            patch("pbn_integrator.utils.mongodb_ops.logger") as mock_logger,
            patch("pbn_integrator.utils.mongodb_ops.rollbar") as mock_rollbar,
        ):
            with pytest.raises(HttpException) as exc_info:
                zapisz_publikacje_instytucji(sample_elem, None, client=mock_client)

            assert exc_info.value.status_code == 404

            # Should NOT log or report for non-500 errors
            mock_logger.warning.assert_not_called()
            mock_rollbar.report_exc_info.assert_not_called()


# ============================================================================
# UNIT TESTS - zapisz_oswiadczenie_instytucji
# ============================================================================


class TestZapiszOswiadczenieInstytucji:
    """Test zapisz_oswiadczenie_instytucji function error handling"""

    @pytest.fixture
    def sample_elem(self):
        """Sample element data for testing"""
        return {
            "id": "12345",
            "publicationId": "pub123",
            "institutionId": "inst456",
            "personId": "person789",
            "addedTimestamp": "2024.01.15",
            "area": "304",
            "inOrcid": False,
            "type": "AUTHOR",
        }

    @pytest.fixture
    def mock_client(self):
        """Mock PBN client"""
        return MagicMock()

    def test_logs_and_reports_on_publication_http_500(self, sample_elem, mock_client):
        """Should log warning and report to rollbar when publication fetch fails"""
        from pbn_integrator.utils.mongodb_ops import zapisz_oswiadczenie_instytucji

        http_exc = HttpException(500, "http://test.url", "Internal Server Error")

        with (
            patch(
                "pbn_integrator.utils.mongodb_ops.ensure_publication_exists",
                side_effect=http_exc,
            ),
            patch("pbn_integrator.utils.mongodb_ops.logger") as mock_logger,
            patch("pbn_integrator.utils.mongodb_ops.rollbar") as mock_rollbar,
        ):
            result = zapisz_oswiadczenie_instytucji(
                sample_elem.copy(), None, client=mock_client
            )

            # Should return early (None)
            assert result is None

            # Should log warning
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert "publikacji" in call_args[0][0]
            assert "oświadczenia" in call_args[0][0]

            # Should report to rollbar
            mock_rollbar.report_exc_info.assert_called_once()

    def test_logs_and_reports_on_institution_http_500(self, sample_elem, mock_client):
        """Should log warning and report to rollbar when institution fetch fails"""
        from pbn_integrator.utils.mongodb_ops import zapisz_oswiadczenie_instytucji

        http_exc = HttpException(500, "http://test.url", "Internal Server Error")

        with (
            patch("pbn_integrator.utils.mongodb_ops.ensure_publication_exists"),
            patch(
                "pbn_integrator.utils.mongodb_ops.ensure_institution_exists",
                side_effect=http_exc,
            ),
            patch("pbn_integrator.utils.mongodb_ops.logger") as mock_logger,
            patch("pbn_integrator.utils.mongodb_ops.rollbar") as mock_rollbar,
        ):
            result = zapisz_oswiadczenie_instytucji(
                sample_elem.copy(), None, client=mock_client
            )

            # Should return early (None)
            assert result is None

            # Should log warning
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert "instytucji" in call_args[0][0]

            # Should report to rollbar
            mock_rollbar.report_exc_info.assert_called_once()

    def test_logs_and_reports_on_person_http_500(self, sample_elem, mock_client):
        """Should log warning and report to rollbar when person fetch fails"""
        from pbn_integrator.utils.mongodb_ops import zapisz_oswiadczenie_instytucji

        http_exc = HttpException(500, "http://test.url", "Internal Server Error")

        with (
            patch("pbn_integrator.utils.mongodb_ops.ensure_publication_exists"),
            patch("pbn_integrator.utils.mongodb_ops.ensure_institution_exists"),
            patch(
                "pbn_integrator.utils.mongodb_ops.ensure_person_exists",
                side_effect=http_exc,
            ),
            patch("pbn_integrator.utils.mongodb_ops.logger") as mock_logger,
            patch("pbn_integrator.utils.mongodb_ops.rollbar") as mock_rollbar,
        ):
            result = zapisz_oswiadczenie_instytucji(
                sample_elem.copy(), None, client=mock_client
            )

            # Should return early (None)
            assert result is None

            # Should log warning
            mock_logger.warning.assert_called_once()
            call_args = mock_logger.warning.call_args
            assert "osoby" in call_args[0][0]

            # Should report to rollbar
            mock_rollbar.report_exc_info.assert_called_once()

    def test_transforms_timestamp_format(self, sample_elem, mock_client):
        """Should transform timestamp from dot to dash format"""
        from pbn_integrator.utils.mongodb_ops import zapisz_oswiadczenie_instytucji

        elem = sample_elem.copy()
        elem["addedTimestamp"] = "2024.01.15"
        elem["statedTimestamp"] = "2024.02.20"

        with (
            patch("pbn_integrator.utils.mongodb_ops.ensure_publication_exists"),
            patch("pbn_integrator.utils.mongodb_ops.ensure_institution_exists"),
            patch("pbn_integrator.utils.mongodb_ops.ensure_person_exists"),
            patch(
                "pbn_integrator.utils.mongodb_ops.OswiadczenieInstytucji"
            ) as mock_model,
        ):
            zapisz_oswiadczenie_instytucji(elem, None, client=mock_client)

            # Verify timestamps were transformed
            call_kwargs = mock_model.objects.update_or_create.call_args[1]
            defaults = call_kwargs["defaults"]
            assert defaults["addedTimestamp"] == "2024-01-15"
            assert defaults["statedTimestamp"] == "2024-02-20"

    def test_does_not_log_on_non_500_http_error(self, sample_elem, mock_client):
        """Should not log or report for non-500 HTTP errors (re-raises)"""
        from pbn_integrator.utils.mongodb_ops import zapisz_oswiadczenie_instytucji

        http_exc = HttpException(404, "http://test.url", "Not Found")

        with (
            patch(
                "pbn_integrator.utils.mongodb_ops.ensure_publication_exists",
                side_effect=http_exc,
            ),
            patch("pbn_integrator.utils.mongodb_ops.logger") as mock_logger,
            patch("pbn_integrator.utils.mongodb_ops.rollbar") as mock_rollbar,
        ):
            with pytest.raises(HttpException) as exc_info:
                zapisz_oswiadczenie_instytucji(
                    sample_elem.copy(), None, client=mock_client
                )

            assert exc_info.value.status_code == 404

            # Should NOT log or report for non-500 errors
            mock_logger.warning.assert_not_called()
            mock_rollbar.report_exc_info.assert_not_called()


# ============================================================================
# UNIT TESTS - zapisz_mongodb
# ============================================================================


class TestZapiszMongodb:
    """Test zapisz_mongodb function"""

    @pytest.fixture
    def sample_elem(self):
        """Sample element data for testing"""
        return {
            "mongoId": "mongo123",
            "status": "ACTIVE",
            "verificationLevel": "HIGH",
            "verified": True,
            "versions": [{"version": 1, "current": True}],
        }

    @pytest.mark.django_db(transaction=True)
    def test_creates_new_record(self, sample_elem):
        """Should create a new record when it doesn't exist"""
        from pbn_api.models import Publication
        from pbn_integrator.utils.mongodb_ops import zapisz_mongodb

        # Clean up any existing record
        Publication.objects.filter(pk=sample_elem["mongoId"]).delete()

        result = zapisz_mongodb(sample_elem, Publication)

        assert result is not None
        assert result.pk == sample_elem["mongoId"]
        assert result.status == "ACTIVE"
        assert result.verified is True

        # Clean up
        result.delete()

    @pytest.mark.django_db(transaction=True)
    def test_updates_existing_record_when_versions_differ(self, sample_elem):
        """Should update existing record when versions differ"""
        from pbn_api.models import Publication
        from pbn_integrator.utils.mongodb_ops import zapisz_mongodb

        # Clean up and create initial record
        Publication.objects.filter(pk=sample_elem["mongoId"]).delete()
        initial = zapisz_mongodb(sample_elem, Publication)

        # Update with new versions
        updated_elem = sample_elem.copy()
        updated_elem["versions"] = [{"version": 2, "current": True}]

        result = zapisz_mongodb(updated_elem, Publication)

        assert result.pk == initial.pk
        assert result.versions == [{"version": 2, "current": True}]

        # Clean up
        result.delete()
