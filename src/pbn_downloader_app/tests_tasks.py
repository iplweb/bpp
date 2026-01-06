"""Tests for pbn_downloader_app Celery tasks."""

from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model
from model_bakery import baker

from pbn_downloader_app.models import (
    PbnDownloadTask,
    PbnInstitutionPeopleTask,
    PbnJournalsDownloadTask,
)
from pbn_downloader_app.tasks import (
    create_task_with_lock,
    download_institution_people,
    download_institution_publications,
    download_journals,
    get_pbn_client,
    mark_task_completed,
    mark_task_failed,
    validate_pbn_user,
)

User = get_user_model()


# ============================================================================
# Helper function tests
# ============================================================================


@pytest.mark.django_db
def test_validate_pbn_user_success():
    """Test validate_pbn_user with valid user and token."""
    user = User.objects.create_user("testuser", password="testpass")

    class MockPbnUser:
        pbn_token = "valid-token"

        def pbn_token_possibly_valid(self):
            return True

    # Mock get_pbn_user on BppUser class, not instance
    with patch("bpp.models.profile.BppUser.get_pbn_user", return_value=MockPbnUser()):
        result_user, result_pbn_user = validate_pbn_user(user.pk)

    assert result_user.pk == user.pk
    assert result_pbn_user.pbn_token == "valid-token"


@pytest.mark.django_db
def test_validate_pbn_user_no_token():
    """Test validate_pbn_user raises ValueError when no token."""
    user = User.objects.create_user("testuser", password="testpass")

    class MockPbnUser:
        pbn_token = None

    with patch("bpp.models.profile.BppUser.get_pbn_user", return_value=MockPbnUser()):
        with pytest.raises(ValueError) as exc_info:
            validate_pbn_user(user.pk)

    assert "not authorized" in str(exc_info.value)


@pytest.mark.django_db
def test_validate_pbn_user_expired_token():
    """Test validate_pbn_user raises ValueError when token is expired."""
    user = User.objects.create_user("testuser", password="testpass")

    class MockPbnUser:
        pbn_token = "expired-token"

        def pbn_token_possibly_valid(self):
            return False

    with patch("bpp.models.profile.BppUser.get_pbn_user", return_value=MockPbnUser()):
        with pytest.raises(ValueError) as exc_info:
            validate_pbn_user(user.pk)

    assert "invalid or expired" in str(exc_info.value)


@pytest.mark.django_db
def test_create_task_with_lock_success():
    """Test create_task_with_lock creates task when none running."""
    user = User.objects.create_user("testuser", password="testpass")

    task = create_task_with_lock(PbnDownloadTask, user, "Starting...")

    assert task.pk is not None
    assert task.status == "running"
    assert task.current_step == "Starting..."
    assert task.progress_percentage == 0


@pytest.mark.django_db
def test_create_task_with_lock_fails_when_running():
    """Test create_task_with_lock raises ValueError when task already running."""
    user = User.objects.create_user("testuser", password="testpass")

    PbnDownloadTask.objects.create(user=user, status="running")

    with pytest.raises(ValueError) as exc_info:
        create_task_with_lock(PbnDownloadTask, user, "Starting...")

    assert "already running" in str(exc_info.value)


@pytest.mark.django_db
def test_mark_task_completed():
    """Test mark_task_completed sets correct status."""
    user = User.objects.create_user("testuser", password="testpass")
    task = PbnDownloadTask.objects.create(user=user, status="running")

    mark_task_completed(task, "Done successfully")

    task.refresh_from_db()
    assert task.status == "completed"
    assert task.current_step == "Done successfully"
    assert task.progress_percentage == 100
    assert task.completed_at is not None


@pytest.mark.django_db
def test_mark_task_failed():
    """Test mark_task_failed sets error status."""
    user = User.objects.create_user("testuser", password="testpass")
    task = PbnDownloadTask.objects.create(user=user, status="running")

    mark_task_failed(task, Exception("Test error"))

    task.refresh_from_db()
    assert task.status == "failed"
    assert "Test error" in task.error_message
    assert task.completed_at is not None


@pytest.mark.django_db
def test_mark_task_failed_handles_none():
    """Test mark_task_failed handles None task_record gracefully."""
    mark_task_failed(None, Exception("Test error"))


@pytest.mark.django_db
def test_get_pbn_client_success(uczelnia):
    """Test get_pbn_client creates client with valid config."""

    class MockPbnUser:
        pbn_token = "valid-token"

    uczelnia.pbn_app_name = "test-app"
    uczelnia.pbn_app_token = "test-app-token"
    uczelnia.pbn_api_root = "https://pbn-api.test/"
    uczelnia.save()

    with patch("pbn_api.client.PBNClient"):
        with patch("pbn_api.client.RequestsTransport") as mock_transport:
            client, returned_uczelnia = get_pbn_client(MockPbnUser())

    mock_transport.assert_called_once_with(
        "test-app", "test-app-token", "https://pbn-api.test/", "valid-token"
    )
    assert returned_uczelnia == uczelnia


@pytest.mark.django_db
def test_get_pbn_client_no_uczelnia():
    """Test get_pbn_client raises ValueError when no default uczelnia."""
    from bpp.models import Uczelnia

    Uczelnia.objects.all().delete()

    class MockPbnUser:
        pbn_token = "valid-token"

    with pytest.raises(ValueError) as exc_info:
        get_pbn_client(MockPbnUser())

    assert "No default institution" in str(exc_info.value)


@pytest.mark.django_db
def test_get_pbn_client_incomplete_config(uczelnia):
    """Test get_pbn_client raises ValueError when config incomplete."""

    class MockPbnUser:
        pbn_token = "valid-token"

    # pbn_app_name has NOT NULL constraint, so use empty string to test
    uczelnia.pbn_app_name = ""
    uczelnia.pbn_app_token = "test-token"
    uczelnia.pbn_api_root = "https://pbn-api.test/"
    uczelnia.save()

    with pytest.raises(ValueError) as exc_info:
        get_pbn_client(MockPbnUser())

    assert "not properly configured" in str(exc_info.value)


# ============================================================================
# download_institution_publications task tests
# ============================================================================


@pytest.mark.django_db
def test_download_institution_publications_already_running():
    """Test download_institution_publications fails when task already running."""
    user = User.objects.create_user("testuser", password="testpass")
    PbnDownloadTask.objects.create(user=user, status="running")

    with pytest.raises(ValueError) as exc_info:
        download_institution_publications(user.pk)

    assert "already running" in str(exc_info.value)


@pytest.mark.django_db
def test_download_institution_publications_success():
    """Test download_institution_publications succeeds with mocked dependencies."""
    user = User.objects.create_user("testuser", password="testpass")

    class MockPbnUser:
        pbn_token = "valid-token"

        def pbn_token_possibly_valid(self):
            return True

    with patch("pbn_downloader_app.tasks.validate_pbn_user") as mock_validate:
        mock_validate.return_value = (user, MockPbnUser())

        # call_command is imported locally, so mock at source
        with patch("django.core.management.call_command") as mock_call:
            with patch("pbn_downloader_app.tasks.tqdm_progress_context"):
                download_institution_publications(user.pk)

    assert mock_call.call_count == 2

    task = PbnDownloadTask.objects.filter(user=user).first()
    assert task is not None
    assert task.status == "completed"


@pytest.mark.django_db
def test_download_institution_publications_handles_error():
    """Test download_institution_publications marks task failed on error."""
    user = User.objects.create_user("testuser", password="testpass")

    class MockPbnUser:
        pbn_token = "valid-token"

        def pbn_token_possibly_valid(self):
            return True

    with patch("pbn_downloader_app.tasks.validate_pbn_user") as mock_validate:
        mock_validate.return_value = (user, MockPbnUser())

        with patch(
            "django.core.management.call_command",
            side_effect=Exception("API Error"),
        ):
            with patch("pbn_downloader_app.tasks.tqdm_progress_context"):
                with pytest.raises(Exception, match="API Error"):
                    download_institution_publications(user.pk)

    task = PbnDownloadTask.objects.filter(user=user).first()
    assert task is not None
    assert task.status == "failed"
    assert "API Error" in task.error_message


# ============================================================================
# download_institution_people task tests
# ============================================================================


@pytest.mark.django_db
def test_download_institution_people_already_running():
    """Test download_institution_people fails when task already running."""
    user = User.objects.create_user("testuser", password="testpass")
    PbnInstitutionPeopleTask.objects.create(user=user, status="running")

    with pytest.raises(ValueError) as exc_info:
        download_institution_people(user.pk)

    assert "already running" in str(exc_info.value)


@pytest.mark.django_db
def test_download_institution_people_no_pbn_uid(uczelnia):
    """Test download_institution_people fails when uczelnia has no PBN UID."""
    user = User.objects.create_user("testuser", password="testpass")

    uczelnia.pbn_uid_id = None
    uczelnia.save()

    class MockPbnUser:
        pbn_token = "valid-token"

        def pbn_token_possibly_valid(self):
            return True

    with patch("pbn_downloader_app.tasks.validate_pbn_user") as mock_validate:
        mock_validate.return_value = (user, MockPbnUser())

        with pytest.raises(ValueError) as exc_info:
            download_institution_people(user.pk)

    assert "PBN UID" in str(exc_info.value)


@pytest.mark.django_db
def test_download_institution_people_success(uczelnia):
    """Test download_institution_people succeeds with mocked dependencies."""
    user = User.objects.create_user("testuser", password="testpass")

    pbn_institution = baker.make("pbn_api.Institution")
    uczelnia.pbn_uid = pbn_institution
    uczelnia.save()

    class MockPbnUser:
        pbn_token = "valid-token"

        def pbn_token_possibly_valid(self):
            return True

    with patch("pbn_downloader_app.tasks.validate_pbn_user") as mock_validate:
        mock_validate.return_value = (user, MockPbnUser())

        with patch("pbn_downloader_app.tasks.tqdm_progress_context"):
            # pobierz_ludzi_z_uczelni is imported locally from pbn_integrator.utils
            with patch("pbn_integrator.utils.pobierz_ludzi_z_uczelni") as mock_pobierz:
                download_institution_people(user.pk)

    mock_pobierz.assert_called_once()

    task = PbnInstitutionPeopleTask.objects.filter(user=user).first()
    assert task is not None
    assert task.status == "completed"


# ============================================================================
# download_journals task tests
# ============================================================================


@pytest.mark.django_db
def test_download_journals_already_running():
    """Test download_journals fails when task already running."""
    user = User.objects.create_user("testuser", password="testpass")
    PbnJournalsDownloadTask.objects.create(user=user, status="running")

    with pytest.raises(ValueError) as exc_info:
        download_journals(user.pk)

    assert "already running" in str(exc_info.value)


@pytest.mark.django_db
def test_download_journals_success(uczelnia):
    """Test download_journals succeeds with mocked dependencies."""
    user = User.objects.create_user("testuser", password="testpass")

    uczelnia.pbn_app_name = "test-app"
    uczelnia.pbn_app_token = "test-app-token"
    uczelnia.pbn_api_root = "https://pbn-api.test/"
    uczelnia.save()

    class MockPbnUser:
        pbn_token = "valid-token"

        def pbn_token_possibly_valid(self):
            return True

    with patch("pbn_downloader_app.tasks.validate_pbn_user") as mock_validate:
        mock_validate.return_value = (user, MockPbnUser())

        with patch("pbn_downloader_app.tasks.get_pbn_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = (mock_client, uczelnia)

            # Local imports from pbn_integrator.utils
            with patch("pbn_integrator.utils.pobierz_zrodla_mnisw") as mock_pobierz:
                with patch("pbn_integrator.utils.integruj_zrodla") as mock_integruj:
                    with patch(
                        "pbn_komparator_zrodel.utils.aktualizuj_brakujace_dyscypliny_pbn"
                    ):
                        download_journals(user.pk)

    mock_pobierz.assert_called_once()
    mock_integruj.assert_called_once()

    task = PbnJournalsDownloadTask.objects.filter(user=user).first()
    assert task is not None
    assert task.status == "completed"


@pytest.mark.django_db
def test_download_journals_handles_error(uczelnia):
    """Test download_journals marks task failed on error."""
    user = User.objects.create_user("testuser", password="testpass")

    uczelnia.pbn_app_name = "test-app"
    uczelnia.pbn_app_token = "test-app-token"
    uczelnia.pbn_api_root = "https://pbn-api.test/"
    uczelnia.save()

    class MockPbnUser:
        pbn_token = "valid-token"

        def pbn_token_possibly_valid(self):
            return True

    with patch("pbn_downloader_app.tasks.validate_pbn_user") as mock_validate:
        mock_validate.return_value = (user, MockPbnUser())

        with patch("pbn_downloader_app.tasks.get_pbn_client") as mock_get_client:
            mock_client = MagicMock()
            mock_get_client.return_value = (mock_client, uczelnia)

            with patch(
                "pbn_integrator.utils.pobierz_zrodla_mnisw",
                side_effect=Exception("API Error"),
            ):
                with pytest.raises(Exception, match="API Error"):
                    download_journals(user.pk)

    task = PbnJournalsDownloadTask.objects.filter(user=user).first()
    assert task is not None
    assert task.status == "failed"
    assert "API Error" in task.error_message


# ============================================================================
# JournalsProgressCallback tests
# ============================================================================


@pytest.mark.django_db
def test_journals_progress_callback():
    """Test JournalsProgressCallback updates task progress."""
    from pbn_downloader_app.tasks import JournalsProgressCallback

    user = User.objects.create_user("testuser", password="testpass")
    task = PbnJournalsDownloadTask.objects.create(
        user=user, status="running", progress_percentage=0
    )

    callback = JournalsProgressCallback(task)
    callback.update(50, 100, "Pobieranie źródeł")

    task.refresh_from_db()
    assert task.journals_processed == 50
    assert task.total_journals == 100
    assert task.progress_percentage > 0
    assert "Pobieranie" in task.current_step


@pytest.mark.django_db
def test_journals_progress_callback_clear():
    """Test JournalsProgressCallback.clear does nothing."""
    from pbn_downloader_app.tasks import JournalsProgressCallback

    user = User.objects.create_user("testuser", password="testpass")
    task = PbnJournalsDownloadTask.objects.create(user=user, status="running")

    callback = JournalsProgressCallback(task)
    callback.clear()


# ============================================================================
# TqdmProgressPatcher tests
# ============================================================================


@pytest.mark.django_db
def test_tqdm_progress_patcher_apply_and_restore():
    """Test TqdmProgressPatcher can apply patches without errors."""
    from pbn_downloader_app.tasks import TqdmProgressPatcher

    user = User.objects.create_user("testuser", password="testpass")
    task = PbnDownloadTask.objects.create(user=user, status="running")

    patcher = TqdmProgressPatcher(task, "_task_record")

    # Apply should not raise
    patcher.apply()

    # Restore should not raise
    patcher.restore()

    # After restore, tqdm should still be importable and usable
    import tqdm

    assert hasattr(tqdm, "tqdm")
