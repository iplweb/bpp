"""Testy re-eksportu kanonicznego zadania pobierania publikacji.

``pbn_api.tasks.download_institution_publications`` to teraz re-eksport
kanonicznej implementacji z ``pbn_downloader_app.tasks`` (koniec z
duplikacją). Tu pilnujemy, że re-eksport działa i że kontrakt
multi-hosted (wymagane uczelnia_id) jest zachowany niezależnie od
ścieżki importu.
"""

from unittest.mock import MagicMock, patch

import pytest
from model_bakery import baker

from bpp.models.profile import BppUser
from pbn_api.tasks import download_institution_publications


def _mock_valid_pbn_user(user):
    mock_pbn_user = MagicMock()
    mock_pbn_user.pbn_token = "valid_token"
    mock_pbn_user.pbn_token_possibly_valid.return_value = True
    return patch.object(type(user), "get_pbn_user", return_value=mock_pbn_user)


@pytest.mark.django_db
def test_reexport_is_canonical():
    """pbn_api.tasks re-eksportuje DOKŁADNIE kanoniczną funkcję."""
    from pbn_downloader_app.tasks import (
        download_institution_publications as canonical,
    )

    assert download_institution_publications is canonical


@pytest.mark.django_db
def test_requires_uczelnia_id(uczelnia):
    """Wywołanie bez uczelnia_id => błąd (kontrakt multi-hosted)."""
    user = baker.make(BppUser)

    with pytest.raises(TypeError):
        download_institution_publications(user.pk)


@pytest.mark.django_db
def test_no_user(uczelnia):
    """Brak użytkownika => BppUser.DoesNotExist."""
    with pytest.raises(BppUser.DoesNotExist):
        download_institution_publications(999999, uczelnia.pk)


@pytest.mark.django_db
def test_no_pbn_token(uczelnia):
    """Użytkownik bez tokenu PBN => ValueError."""
    user = baker.make(BppUser)

    with pytest.raises(ValueError, match="not authorized"):
        download_institution_publications(user.pk, uczelnia.pk)


@pytest.mark.django_db
def test_concurrent_task_running(uczelnia):
    """Inne działające zadanie => ValueError 'already running'."""
    from pbn_downloader_app.models import PbnDownloadTask

    user = baker.make(BppUser)
    baker.make(PbnDownloadTask, status="running")

    with _mock_valid_pbn_user(user):
        with pytest.raises(ValueError, match="already running"):
            download_institution_publications(user.pk, uczelnia.pk)


@pytest.mark.django_db
def test_runs_both_commands_with_uczelnia_id(uczelnia):
    """Sukces: obie komendy odpalone, z poprawnym uczelnia_id i tokenem."""
    from pbn_downloader_app.models import PbnDownloadTask

    user = baker.make(BppUser)

    with _mock_valid_pbn_user(user):
        with patch("django.core.management.call_command") as mock_call:
            with patch("pbn_downloader_app.tasks.tqdm_progress_context"):
                download_institution_publications(user.pk, uczelnia.pk)

    assert mock_call.call_count == 2

    first = mock_call.call_args_list[0]
    assert first[0][0] == "pbn_pobierz_publikacje_z_instytucji_v2"
    assert first[1]["user_token"] == "valid_token"
    assert first[1]["uczelnia_id"] == uczelnia.pk

    second = mock_call.call_args_list[1]
    assert second[0][0] == "pbn_pobierz_oswiadczenia_i_publikacje_v1"
    assert second[1]["uczelnia_id"] == uczelnia.pk

    task = PbnDownloadTask.objects.first()
    assert task.status == "completed"


@pytest.mark.django_db
def test_error_marks_as_failed(uczelnia):
    """Błąd komendy => zadanie oznaczone jako failed."""
    from pbn_downloader_app.models import PbnDownloadTask

    user = baker.make(BppUser)

    with _mock_valid_pbn_user(user):
        with patch(
            "django.core.management.call_command",
            side_effect=Exception("Test error"),
        ):
            with patch("pbn_downloader_app.tasks.tqdm_progress_context"):
                with pytest.raises(Exception, match="Test error"):
                    download_institution_publications(user.pk, uczelnia.pk)

    task = PbnDownloadTask.objects.first()
    assert task.status == "failed"
    assert "Test error" in task.error_message
