import logging
import sys
from contextlib import contextmanager
from threading import Lock

import rollbar
from django.core.management import call_command

from django_bpp.celery_tasks import app

logger = logging.getLogger(__name__)


def _validate_user_pbn_access(user_id):
    """
    Sprawdza czy użytkownik ma dostęp do PBN.

    Returns:
        tuple: (user, pbn_user) jeśli walidacja przeszła

    Raises:
        ValueError: jeśli użytkownik nie ma dostępu
    """
    from bpp.models.profile import BppUser

    user = BppUser.objects.get(pk=user_id)
    pbn_user = user.get_pbn_user()

    if not pbn_user.pbn_token:
        raise ValueError(
            f"User {user.username} is not authorized in PBN (no pbn_token)"
        )

    if not pbn_user.pbn_token_possibly_valid():
        raise ValueError(f"User {user.username} has an invalid or expired PBN token")

    return user, pbn_user


def _create_task_record(user, task_model):
    """
    Tworzy rekord zadania z blokadą transakcji.

    Returns:
        PbnDownloadTask: nowy rekord zadania

    Raises:
        ValueError: jeśli inne zadanie już działa
    """
    from django.db import transaction
    from django.utils import timezone

    with transaction.atomic():
        if task_model.objects.filter(status="running").exists():
            raise ValueError(
                "Another download task is already running. "
                "Please wait for it to complete."
            )

        return task_model.objects.create(
            user=user,
            status="running",
            started_at=timezone.now(),
            current_step="Inicjalizacja pobierania...",
            progress_percentage=0,
        )


def _mark_task_completed(task_record):
    """Oznacza zadanie jako zakończone."""
    from django.utils import timezone

    task_record.status = "completed"
    task_record.current_step = "Pobieranie zakończone pomyślnie"
    task_record.progress_percentage = 100
    task_record.completed_at = timezone.now()
    task_record.save()


def _mark_task_failed(task_record, error):
    """Oznacza zadanie jako nieudane."""
    from django.utils import timezone

    if task_record:
        task_record.status = "failed"
        task_record.error_message = str(error)
        task_record.completed_at = timezone.now()
        task_record.save()


@contextmanager
def _tqdm_progress_patcher(task_record):
    """
    Context manager do patchowania tqdm dla raportowania postępu.
    """
    import tqdm

    original_init = tqdm.tqdm.__init__
    original_update = tqdm.tqdm.update
    original_close = tqdm.tqdm.close
    progress_lock = Lock()

    def patched_init(self, iterable=None, desc=None, total=None, *args, **kwargs):
        self._task_record = task_record
        self._desc = desc or ""
        # Determine phase offset based on current step
        if task_record.current_step and "Faza 1" in task_record.current_step:
            self._phase_offset = 10
        elif task_record.current_step and "Faza 2" in task_record.current_step:
            self._phase_offset = 50
        else:
            self._phase_offset = 10
        original_init(self, iterable, desc, total, *args, **kwargs)

    def patched_update(self, n=1):
        result = original_update(self, n)
        if hasattr(self, "_task_record") and self._task_record:
            _update_progress_from_tqdm(self, progress_lock)
        return result

    def patched_close(self):
        result = original_close(self)
        if hasattr(self, "_task_record") and self._task_record:
            _finalize_progress_from_tqdm(self, progress_lock)
        return result

    # Apply patches
    tqdm.tqdm.__init__ = patched_init
    tqdm.tqdm.update = patched_update
    tqdm.tqdm.close = patched_close

    try:
        yield
    finally:
        # Restore original methods
        tqdm.tqdm.__init__ = original_init
        tqdm.tqdm.update = original_update
        tqdm.tqdm.close = original_close


def _update_progress_from_tqdm(tqdm_instance, lock):
    """Aktualizuje postęp zadania na podstawie stanu tqdm."""
    with lock:
        try:
            task = tqdm_instance._task_record
            if not tqdm_instance.total or tqdm_instance.total <= 0:
                return

            # Calculate progress
            command_progress = (tqdm_instance.n / tqdm_instance.total) * 35
            total_progress = tqdm_instance._phase_offset + command_progress
            task.progress_percentage = min(90, max(10, int(total_progress)))

            # Update publication/statement counts
            if tqdm_instance._desc:
                _update_task_counters(task, tqdm_instance)

            task.save()
        except Exception:
            rollbar.report_exc_info(sys.exc_info())
            logger.debug("Błąd aktualizacji postępu zadania", exc_info=True)


def _update_task_counters(task, tqdm_instance):
    """Aktualizuje liczniki publikacji/oświadczeń w zadaniu."""
    desc = tqdm_instance._desc.lower()

    if "publikacj" in desc:
        task.publications_processed = tqdm_instance.n
        if tqdm_instance.total:
            task.total_publications = tqdm_instance.total
    elif "oświadczen" in desc or "statement" in desc:
        task.statements_processed = tqdm_instance.n
        if tqdm_instance.total:
            task.total_statements = tqdm_instance.total

    # Update step description
    progress_text = f"{tqdm_instance._desc} ({tqdm_instance.n}"
    if tqdm_instance.total:
        progress_text += f"/{tqdm_instance.total}"
    progress_text += ")"
    task.current_step = progress_text


def _finalize_progress_from_tqdm(tqdm_instance, lock):
    """Finalizuje postęp po zamknięciu tqdm."""
    with lock:
        try:
            task = tqdm_instance._task_record
            if tqdm_instance.total and tqdm_instance.n >= tqdm_instance.total:
                total_progress = tqdm_instance._phase_offset + 35
                task.progress_percentage = min(90, int(total_progress))
                task.save()
        except Exception:
            rollbar.report_exc_info(sys.exc_info())
            logger.debug("Błąd aktualizacji postępu zadania (close)", exc_info=True)


def _run_pbn_download_commands(task_record, pbn_token):
    """Uruchamia komendy pobierania z PBN."""
    task_record.current_step = "Pobieranie publikacji instytucji (Faza 1/2)"
    task_record.progress_percentage = 10
    task_record.save()

    call_command("pbn_pobierz_publikacje_z_instytucji_v2", user_token=pbn_token)

    task_record.current_step = "Pobieranie oświadczeń i publikacji (Faza 2/2)"
    task_record.progress_percentage = 50
    task_record.save()

    call_command("pbn_pobierz_oswiadczenia_i_publikacje_v1", user_token=pbn_token)

    task_record.current_step = "Finalizowanie pobierania..."
    task_record.progress_percentage = 90
    task_record.save()


@app.task
def download_institution_publications(user_id):
    """
    Download institution publications using PBN API management commands.
    Uses database-based locking to ensure only one instance runs at a time.

    Args:
        user_id: ID of the user initiating the download (must have valid PBN token)
    """
    from pbn_downloader_app.models import PbnDownloadTask

    # Check for running tasks
    if PbnDownloadTask.objects.filter(status="running").exists():
        raise ValueError(
            "Another download task is already running. Please wait for it to complete."
        )

    task_record = None
    try:
        user, pbn_user = _validate_user_pbn_access(user_id)
        task_record = _create_task_record(user, PbnDownloadTask)

        with _tqdm_progress_patcher(task_record):
            _run_pbn_download_commands(task_record, pbn_user.pbn_token)

        _mark_task_completed(task_record)

    except Exception as e:
        _mark_task_failed(task_record, e)
        raise
