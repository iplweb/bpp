import pytest
from django.utils import timezone
from model_bakery import baker
from unittest.mock import patch, MagicMock, call

from pbn_api.tasks import download_institution_publications
from bpp.models.profile import BppUser


@pytest.mark.django_db
def test_download_institution_publications_no_user():
    """Test task raises error when user not found"""
    with pytest.raises(BppUser.DoesNotExist):
        download_institution_publications(999999)


@pytest.mark.django_db
def test_download_institution_publications_no_pbn_token():
    """Test task raises error when user has no PBN token"""
    user = baker.make(BppUser)

    with pytest.raises(ValueError, match="not authorized"):
        download_institution_publications(user.pk)


@pytest.mark.django_db
def test_download_institution_publications_invalid_token():
    """Test task raises error when user has invalid/expired token"""
    user = baker.make(BppUser)
    user.pbn_token = "expired_token"
    user.pbn_token_updated = timezone.now() - timezone.timedelta(days=100)
    user.save()

    # Mock pbn_token_possibly_valid to return False
    with patch.object(type(user), "get_pbn_user") as mock_get_pbn:
        mock_pbn_user = MagicMock()
        mock_pbn_user.pbn_token = "expired_token"
        mock_pbn_user.pbn_token_possibly_valid.return_value = False
        mock_get_pbn.return_value = mock_pbn_user

        with pytest.raises(ValueError, match="invalid or expired"):
            download_institution_publications(user.pk)


@pytest.mark.django_db
def test_download_institution_publications_concurrent_task_running():
    """Test task raises error when another task is already running"""
    from pbn_downloader_app.models import PbnDownloadTask

    user = baker.make(BppUser)
    user.pbn_token = "valid_token"
    user.save()

    # Create a running task
    baker.make(PbnDownloadTask, status="running")

    with patch.object(type(user), "get_pbn_user") as mock_get_pbn:
        mock_pbn_user = MagicMock()
        mock_pbn_user.pbn_token = "valid_token"
        mock_pbn_user.pbn_token_possibly_valid.return_value = True
        mock_get_pbn.return_value = mock_pbn_user

        with pytest.raises(ValueError, match="already running"):
            download_institution_publications(user.pk)


@pytest.mark.django_db
@patch("pbn_api.tasks.call_command")
def test_download_institution_publications_creates_task_record(mock_call_command):
    """Test task creates PbnDownloadTask record"""
    from pbn_downloader_app.models import PbnDownloadTask

    user = baker.make(BppUser)
    user.pbn_token = "valid_token"
    user.save()

    with patch.object(type(user), "get_pbn_user") as mock_get_pbn:
        mock_pbn_user = MagicMock()
        mock_pbn_user.pbn_token = "valid_token"
        mock_pbn_user.pbn_token_possibly_valid.return_value = True
        mock_get_pbn.return_value = mock_pbn_user

        download_institution_publications(user.pk)

        # Verify task record was created and marked as completed
        task = PbnDownloadTask.objects.first()
        assert task is not None
        assert task.user == user
        assert task.status == "completed"


@pytest.mark.django_db
@patch("pbn_api.tasks.call_command")
def test_download_institution_publications_runs_both_commands(mock_call_command):
    """Test task runs both download management commands"""
    from pbn_downloader_app.models import PbnDownloadTask

    user = baker.make(BppUser)
    user.pbn_token = "valid_token"
    user.save()

    with patch.object(type(user), "get_pbn_user") as mock_get_pbn:
        mock_pbn_user = MagicMock()
        mock_pbn_user.pbn_token = "valid_token"
        mock_pbn_user.pbn_token_possibly_valid.return_value = True
        mock_get_pbn.return_value = mock_pbn_user

        download_institution_publications(user.pk)

        # Verify both commands were called
        assert mock_call_command.call_count == 2


@pytest.mark.django_db
@patch("pbn_api.tasks.call_command")
def test_download_institution_publications_first_command_correct(mock_call_command):
    """Test task calls first command with correct arguments"""
    user = baker.make(BppUser)
    user.pbn_token = "valid_token"
    user.save()

    with patch.object(type(user), "get_pbn_user") as mock_get_pbn:
        mock_pbn_user = MagicMock()
        mock_pbn_user.pbn_token = "valid_token"
        mock_pbn_user.pbn_token_possibly_valid.return_value = True
        mock_get_pbn.return_value = mock_pbn_user

        download_institution_publications(user.pk)

        # Check first command call
        first_call = mock_call_command.call_args_list[0]
        assert first_call[0][0] == "pbn_pobierz_publikacje_z_instytucji_v2"
        assert first_call[1]["user_token"] == "valid_token"


@pytest.mark.django_db
@patch("pbn_api.tasks.call_command")
def test_download_institution_publications_second_command_correct(mock_call_command):
    """Test task calls second command with correct arguments"""
    user = baker.make(BppUser)
    user.pbn_token = "valid_token"
    user.save()

    with patch.object(type(user), "get_pbn_user") as mock_get_pbn:
        mock_pbn_user = MagicMock()
        mock_pbn_user.pbn_token = "valid_token"
        mock_pbn_user.pbn_token_possibly_valid.return_value = True
        mock_get_pbn.return_value = mock_pbn_user

        download_institution_publications(user.pk)

        # Check second command call
        second_call = mock_call_command.call_args_list[1]
        assert second_call[0][0] == "pbn_pobierz_oswiadczenia_i_publikacje_v1"
        assert second_call[1]["user_token"] == "valid_token"


@pytest.mark.django_db
@patch("pbn_api.tasks.call_command")
def test_download_institution_publications_sets_progress(mock_call_command):
    """Test task updates progress in database"""
    from pbn_downloader_app.models import PbnDownloadTask

    user = baker.make(BppUser)
    user.pbn_token = "valid_token"
    user.save()

    with patch.object(type(user), "get_pbn_user") as mock_get_pbn:
        mock_pbn_user = MagicMock()
        mock_pbn_user.pbn_token = "valid_token"
        mock_pbn_user.pbn_token_possibly_valid.return_value = True
        mock_get_pbn.return_value = mock_pbn_user

        download_institution_publications(user.pk)

        task = PbnDownloadTask.objects.first()

        # Check that progress was set to 100
        assert task.progress_percentage == 100


@pytest.mark.django_db
@patch("pbn_api.tasks.call_command")
def test_download_institution_publications_sets_completion_time(mock_call_command):
    """Test task sets completion time"""
    from pbn_downloader_app.models import PbnDownloadTask

    user = baker.make(BppUser)
    user.pbn_token = "valid_token"
    user.save()

    before = timezone.now()

    with patch.object(type(user), "get_pbn_user") as mock_get_pbn:
        mock_pbn_user = MagicMock()
        mock_pbn_user.pbn_token = "valid_token"
        mock_pbn_user.pbn_token_possibly_valid.return_value = True
        mock_get_pbn.return_value = mock_pbn_user

        download_institution_publications(user.pk)

    after = timezone.now()
    task = PbnDownloadTask.objects.first()

    assert task.completed_at is not None
    assert before <= task.completed_at <= after


@pytest.mark.django_db
@patch("pbn_api.tasks.call_command")
def test_download_institution_publications_error_marks_as_failed(mock_call_command):
    """Test task marks task as failed on error"""
    from pbn_downloader_app.models import PbnDownloadTask

    user = baker.make(BppUser)
    user.pbn_token = "valid_token"
    user.save()

    mock_call_command.side_effect = Exception("Test error")

    with patch.object(type(user), "get_pbn_user") as mock_get_pbn:
        mock_pbn_user = MagicMock()
        mock_pbn_user.pbn_token = "valid_token"
        mock_pbn_user.pbn_token_possibly_valid.return_value = True
        mock_get_pbn.return_value = mock_pbn_user

        with pytest.raises(Exception):
            download_institution_publications(user.pk)

    task = PbnDownloadTask.objects.first()
    assert task.status == "failed"
    assert task.error_message == "Test error"


@pytest.mark.django_db
@patch("pbn_api.tasks.call_command")
def test_download_institution_publications_error_saves_completion_time(
    mock_call_command,
):
    """Test task saves completion time on error"""
    from pbn_downloader_app.models import PbnDownloadTask

    user = baker.make(BppUser)
    user.pbn_token = "valid_token"
    user.save()

    mock_call_command.side_effect = Exception("Test error")

    before = timezone.now()

    with patch.object(type(user), "get_pbn_user") as mock_get_pbn:
        mock_pbn_user = MagicMock()
        mock_pbn_user.pbn_token = "valid_token"
        mock_pbn_user.pbn_token_possibly_valid.return_value = True
        mock_get_pbn.return_value = mock_pbn_user

        with pytest.raises(Exception):
            download_institution_publications(user.pk)

    after = timezone.now()
    task = PbnDownloadTask.objects.first()

    assert task.completed_at is not None
    assert before <= task.completed_at <= after


@pytest.mark.django_db
@patch("pbn_api.tasks.call_command")
def test_download_institution_publications_sets_initial_status(mock_call_command):
    """Test task starts with running status"""
    from pbn_downloader_app.models import PbnDownloadTask

    user = baker.make(BppUser)
    user.pbn_token = "valid_token"
    user.save()

    with patch.object(type(user), "get_pbn_user") as mock_get_pbn:
        mock_pbn_user = MagicMock()
        mock_pbn_user.pbn_token = "valid_token"
        mock_pbn_user.pbn_token_possibly_valid.return_value = True
        mock_get_pbn.return_value = mock_pbn_user

        download_institution_publications(user.pk)

    task = PbnDownloadTask.objects.first()

    # Should be completed after successful run
    assert task.status == "completed"
