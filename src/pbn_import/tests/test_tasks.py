"""Tests for pbn_import Celery tasks."""

from unittest.mock import MagicMock, patch

import pytest
from model_bakery import baker

from pbn_import.models import ImportLog, ImportSession
from pbn_import.tasks import run_pbn_import, send_websocket_update, update_progress

# ============================================================================
# Helper function tests
# ============================================================================


@pytest.mark.django_db
def test_send_websocket_update_success():
    """Test send_websocket_update sends update via channel layer."""
    session = baker.make(ImportSession)

    with patch("pbn_import.tasks.get_channel_layer") as mock_get_layer:
        mock_layer = MagicMock()
        mock_get_layer.return_value = mock_layer

        with patch("pbn_import.tasks.async_to_sync") as mock_async:
            mock_send = MagicMock()
            mock_async.return_value = mock_send

            send_websocket_update(session, {"type": "test", "progress": 50})

            mock_send.assert_called_once()


@pytest.mark.django_db
def test_send_websocket_update_no_channel_layer():
    """Test send_websocket_update handles no channel layer gracefully."""
    session = baker.make(ImportSession)

    with patch("pbn_import.tasks.get_channel_layer", return_value=None):
        send_websocket_update(session, {"type": "test"})


@pytest.mark.django_db
def test_send_websocket_update_handles_exception():
    """Test send_websocket_update handles exceptions gracefully."""
    session = baker.make(ImportSession)

    with patch("pbn_import.tasks.get_channel_layer") as mock_get_layer:
        mock_layer = MagicMock()
        mock_get_layer.return_value = mock_layer

        with patch(
            "pbn_import.tasks.async_to_sync", side_effect=Exception("WebSocket error")
        ):
            send_websocket_update(session, {"type": "test"})


@pytest.mark.django_db
def test_update_progress():
    """Test update_progress updates session and creates log."""
    session = baker.make(ImportSession, current_step="", current_step_progress=0)

    with patch("pbn_import.tasks.send_websocket_update"):
        update_progress(session, "Importing authors", 50, "Processing 100 authors")

    session.refresh_from_db()
    assert session.current_step == "Importing authors"
    assert session.current_step_progress == 50

    log = ImportLog.objects.filter(session=session, step="Importing authors").first()
    assert log is not None
    assert log.message == "Processing 100 authors"


@pytest.mark.django_db
def test_update_progress_without_message():
    """Test update_progress works without message."""
    session = baker.make(ImportSession, current_step="", current_step_progress=0)

    with patch("pbn_import.tasks.send_websocket_update"):
        update_progress(session, "Step 1", 25, message=None)

    session.refresh_from_db()
    assert session.current_step == "Step 1"
    assert session.current_step_progress == 25

    assert not ImportLog.objects.filter(
        session=session, step="Step 1", message__isnull=False
    ).exists()


# ============================================================================
# run_pbn_import task tests
# ============================================================================


@pytest.mark.django_db
def test_run_pbn_import_session_not_found():
    """Test run_pbn_import handles missing session gracefully."""
    # Task doesn't raise exception, just logs error and returns
    with patch("pbn_import.tasks.logger") as mock_logger:
        run_pbn_import.apply(args=(99999,))

    # Verify the error was logged
    mock_logger.error.assert_called_once_with("Sesja 99999 nie została znaleziona")


@pytest.mark.django_db
def test_run_pbn_import_success(uczelnia, admin_user):
    """Test run_pbn_import completes successfully with mocked dependencies."""
    session = ImportSession.objects.create(
        user=admin_user, status="pending", config={"test": "config"}
    )

    mock_import_manager = MagicMock()
    mock_import_manager.run.return_value = {"success": True}

    with patch("pbn_import.tasks.send_websocket_update"):
        with patch("pbn_import.tasks.ImportManager", return_value=mock_import_manager):
            with patch.object(uczelnia, "pbn_client", return_value=MagicMock()):
                run_pbn_import.apply(args=(session.pk,))

    session.refresh_from_db()
    assert session.status == "completed"
    assert session.completed_at is not None

    log = ImportLog.objects.filter(session=session, step="End").first()
    assert log is not None


@pytest.mark.django_db
def test_run_pbn_import_marks_running(uczelnia, admin_user):
    """Test run_pbn_import marks session as running."""
    session = ImportSession.objects.create(user=admin_user, status="pending", config={})

    mock_import_manager = MagicMock()
    mock_import_manager.run.return_value = {"success": True}

    with patch("pbn_import.tasks.send_websocket_update"):
        with patch("pbn_import.tasks.ImportManager", return_value=mock_import_manager):
            with patch.object(uczelnia, "pbn_client", return_value=MagicMock()):
                run_pbn_import.apply(args=(session.pk,))

    session.refresh_from_db()
    assert session.task_id is not None


@pytest.mark.django_db
def test_run_pbn_import_handles_no_pbn_client(uczelnia, admin_user):
    """Test run_pbn_import handles case when PBN client cannot be created."""
    session = ImportSession.objects.create(user=admin_user, status="pending", config={})

    mock_import_manager = MagicMock()
    mock_import_manager.run.return_value = {"success": True}

    with patch("pbn_import.tasks.send_websocket_update"):
        with patch("pbn_import.tasks.ImportManager", return_value=mock_import_manager):
            with patch.object(
                uczelnia, "pbn_client", side_effect=Exception("No PBN config")
            ):
                run_pbn_import.apply(args=(session.pk,))

    session.refresh_from_db()
    assert session.status == "completed"

    log = ImportLog.objects.filter(
        session=session, step="Setup", level="warning"
    ).first()
    assert log is not None


@pytest.mark.django_db
def test_run_pbn_import_failure(uczelnia, admin_user):
    """Test run_pbn_import marks session as failed on error."""
    session = ImportSession.objects.create(user=admin_user, status="pending", config={})

    mock_import_manager = MagicMock()
    mock_import_manager.run.side_effect = Exception("Import failed")

    with patch("pbn_import.tasks.send_websocket_update"):
        with patch("pbn_import.tasks.ImportManager", return_value=mock_import_manager):
            with patch.object(uczelnia, "pbn_client", return_value=MagicMock()):
                with patch("pbn_import.tasks.rollbar"):
                    run_pbn_import.apply(args=(session.pk,))

    session.refresh_from_db()
    assert session.status == "failed"
    assert "Import failed" in session.error_message
    assert session.error_traceback is not None

    log = ImportLog.objects.filter(session=session, level="critical").first()
    assert log is not None


@pytest.mark.django_db
def test_run_pbn_import_cancelled(uczelnia, admin_user):
    """Test run_pbn_import respects cancelled status set during import."""
    session = ImportSession.objects.create(user=admin_user, status="pending", config={})

    def simulate_cancellation(sess, pbn_client, config):
        """Simulate ImportManager that detects cancellation during run."""
        # During run, session gets cancelled (e.g., user cancels via UI)
        sess.status = "cancelled"
        sess.save()
        mock_manager = MagicMock()
        mock_manager.run.return_value = {"success": False}
        return mock_manager

    with patch("pbn_import.tasks.send_websocket_update"):
        with patch("pbn_import.tasks.ImportManager", side_effect=simulate_cancellation):
            with patch.object(uczelnia, "pbn_client", return_value=MagicMock()):
                run_pbn_import.apply(args=(session.pk,))

    session.refresh_from_db()
    assert session.status == "cancelled"


@pytest.mark.django_db
def test_run_pbn_import_failed_result(uczelnia, admin_user):
    """Test run_pbn_import marks session as failed when result has no success."""
    session = ImportSession.objects.create(user=admin_user, status="pending", config={})

    mock_import_manager = MagicMock()
    mock_import_manager.run.return_value = {"success": False, "error": "Some error"}

    with patch("pbn_import.tasks.send_websocket_update"):
        with patch("pbn_import.tasks.ImportManager", return_value=mock_import_manager):
            with patch.object(uczelnia, "pbn_client", return_value=MagicMock()):
                run_pbn_import.apply(args=(session.pk,))

    session.refresh_from_db()
    assert session.status == "failed"


@pytest.mark.django_db
def test_run_pbn_import_sends_completion_notification(uczelnia, admin_user):
    """Test run_pbn_import sends completion WebSocket notification."""
    session = ImportSession.objects.create(user=admin_user, status="pending", config={})

    mock_import_manager = MagicMock()
    mock_import_manager.run.return_value = {"success": True}

    websocket_calls = []

    def track_websocket(sess, data):
        websocket_calls.append(data)

    with patch("pbn_import.tasks.send_websocket_update", side_effect=track_websocket):
        with patch("pbn_import.tasks.ImportManager", return_value=mock_import_manager):
            with patch.object(uczelnia, "pbn_client", return_value=MagicMock()):
                run_pbn_import.apply(args=(session.pk,))

    completion_call = next(
        (c for c in websocket_calls if c.get("type") == "completion"), None
    )
    assert completion_call is not None
    assert completion_call["success"] is True


@pytest.mark.django_db
def test_run_pbn_import_creates_start_log(uczelnia, admin_user):
    """Test run_pbn_import creates start log entry."""
    session = ImportSession.objects.create(user=admin_user, status="pending", config={})

    mock_import_manager = MagicMock()
    mock_import_manager.run.return_value = {"success": True}

    with patch("pbn_import.tasks.send_websocket_update"):
        with patch("pbn_import.tasks.ImportManager", return_value=mock_import_manager):
            with patch.object(uczelnia, "pbn_client", return_value=MagicMock()):
                run_pbn_import.apply(args=(session.pk,))

    start_log = ImportLog.objects.filter(
        session=session, step="Start", level="info"
    ).first()
    assert start_log is not None
    assert "rozpoczęty" in start_log.message
