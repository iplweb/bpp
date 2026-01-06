"""Tests for deduplikator_autorow Celery tasks."""

from unittest.mock import MagicMock

import pytest

from deduplikator_autorow.models import (
    DuplicateScanRun,
)
from deduplikator_autorow.tasks import (
    _get_main_autor_from_osoba,
    _get_user_by_id,
    _process_duplicate_info,
    cancel_scan,
    normalize_confidence,
)

# ============================================================================
# Helper function tests
# ============================================================================


def test_normalize_confidence_min():
    """Test normalize_confidence with minimum value."""
    from deduplikator_autorow.utils.constants import MIN_PEWNOSC

    result = normalize_confidence(MIN_PEWNOSC)
    assert result == 0.0


def test_normalize_confidence_max():
    """Test normalize_confidence with maximum value."""
    from deduplikator_autorow.utils.constants import MAX_PEWNOSC

    result = normalize_confidence(MAX_PEWNOSC)
    assert result == 1.0


def test_normalize_confidence_middle():
    """Test normalize_confidence with middle value."""
    from deduplikator_autorow.utils.constants import MAX_PEWNOSC, MIN_PEWNOSC

    middle = (MIN_PEWNOSC + MAX_PEWNOSC) // 2
    result = normalize_confidence(middle)
    assert 0.4 <= result <= 0.6


def test_normalize_confidence_below_min():
    """Test normalize_confidence clamps values below min to 0."""
    from deduplikator_autorow.utils.constants import MIN_PEWNOSC

    result = normalize_confidence(MIN_PEWNOSC - 100)
    assert result == 0.0


def test_normalize_confidence_above_max():
    """Test normalize_confidence clamps values above max to 1."""
    from deduplikator_autorow.utils.constants import MAX_PEWNOSC

    result = normalize_confidence(MAX_PEWNOSC + 100)
    assert result == 1.0


@pytest.mark.django_db
def test_get_user_by_id_success(admin_user):
    """Test _get_user_by_id returns user when found."""
    result = _get_user_by_id(admin_user.pk)
    assert result == admin_user


@pytest.mark.django_db
def test_get_user_by_id_none():
    """Test _get_user_by_id returns None when user_id is None."""
    result = _get_user_by_id(None)
    assert result is None


@pytest.mark.django_db
def test_get_user_by_id_not_found():
    """Test _get_user_by_id returns None when user not found."""
    result = _get_user_by_id(99999)
    assert result is None


@pytest.mark.django_db
def test_get_main_autor_from_osoba_no_person_id():
    """Test _get_main_autor_from_osoba returns None when no personId."""
    mock_osoba = MagicMock()
    mock_osoba.personId = None

    result = _get_main_autor_from_osoba(mock_osoba)
    assert result is None


@pytest.mark.django_db
def test_get_main_autor_from_osoba_no_rekord_w_bpp():
    """Test _get_main_autor_from_osoba returns None when no rekord_w_bpp."""
    mock_osoba = MagicMock()
    mock_osoba.personId = MagicMock()
    mock_osoba.personId.rekord_w_bpp = None

    result = _get_main_autor_from_osoba(mock_osoba)
    assert result is None


@pytest.mark.django_db
def test_get_main_autor_from_osoba_success(autor_jan_kowalski):
    """Test _get_main_autor_from_osoba returns autor when found."""
    mock_scientist = MagicMock()
    mock_scientist.rekord_w_bpp = autor_jan_kowalski

    mock_osoba = MagicMock()
    mock_osoba.personId = mock_scientist

    result = _get_main_autor_from_osoba(mock_osoba)
    assert result == autor_jan_kowalski


# ============================================================================
# cancel_scan task tests
# ============================================================================


@pytest.mark.django_db
def test_cancel_scan_success():
    """Test cancel_scan successfully cancels running scan."""
    scan_run = DuplicateScanRun.objects.create(status=DuplicateScanRun.Status.RUNNING)

    result = cancel_scan.apply(args=(scan_run.pk,)).result

    assert result["status"] == "success"
    assert result["scan_run_id"] == scan_run.pk

    scan_run.refresh_from_db()
    assert scan_run.status == DuplicateScanRun.Status.CANCELLED
    assert scan_run.finished_at is not None


@pytest.mark.django_db
def test_cancel_scan_not_running():
    """Test cancel_scan fails when scan is not running."""
    scan_run = DuplicateScanRun.objects.create(status=DuplicateScanRun.Status.COMPLETED)

    result = cancel_scan.apply(args=(scan_run.pk,)).result

    assert result["status"] == "error"
    assert "not running" in result["error"]


@pytest.mark.django_db
def test_cancel_scan_not_found():
    """Test cancel_scan fails when scan not found."""
    result = cancel_scan.apply(args=(99999,)).result

    assert result["status"] == "error"
    assert "not found" in result["error"]


# ============================================================================
# _process_duplicate_info tests
# ============================================================================


@pytest.mark.django_db
def test_process_duplicate_info_below_confidence():
    """Test _process_duplicate_info returns None when confidence too low."""
    duplikat_info = {"pewnosc": 30, "autor": MagicMock()}

    result = _process_duplicate_info(
        duplikat_info,
        MagicMock(),  # scan_run
        MagicMock(),  # main_autor
        MagicMock(),  # osoba_z_instytucji
        10,  # main_pub_count
        50,  # min_confidence
    )

    assert result is None


@pytest.mark.django_db
def test_process_duplicate_info_no_autor():
    """Test _process_duplicate_info returns None when no autor in info."""
    duplikat_info = {"pewnosc": 80, "autor": None}

    result = _process_duplicate_info(
        duplikat_info,
        MagicMock(),
        MagicMock(),
        MagicMock(),
        10,
        50,
    )

    assert result is None
