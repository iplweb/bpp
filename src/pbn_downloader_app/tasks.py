import logging
import sys
from contextlib import contextmanager
from threading import Lock

import rollbar

from django_bpp.celery_tasks import app

logger = logging.getLogger(__name__)


class TqdmProgressPatcher:
    """
    Helper class to patch tqdm for progress tracking.
    Allows updating a task record based on tqdm progress.
    """

    def __init__(self, task_record, task_attr_name, phase_offset=10, phase_range=35):
        self.task_record = task_record
        self.task_attr_name = task_attr_name
        self.phase_offset = phase_offset
        self.phase_range = phase_range
        self.progress_lock = Lock()

        # Store original methods
        import tqdm

        self.tqdm = tqdm
        self.original_init = tqdm.tqdm.__init__
        self.original_update = tqdm.tqdm.update
        self.original_close = tqdm.tqdm.close

    def _create_patched_init(self):
        task_record = self.task_record
        task_attr_name = self.task_attr_name
        phase_offset = self.phase_offset
        original_init = self.original_init

        def patched_tqdm_init(
            tqdm_self, iterable=None, desc=None, total=None, *args, **kwargs
        ):
            setattr(tqdm_self, task_attr_name, task_record)
            tqdm_self._desc = desc or ""
            tqdm_self._phase_offset = phase_offset
            original_init(tqdm_self, iterable, desc, total, *args, **kwargs)

        return patched_tqdm_init

    def _create_patched_update(self, progress_fields_callback):
        task_attr_name = self.task_attr_name
        phase_range = self.phase_range
        progress_lock = self.progress_lock
        original_update = self.original_update

        def patched_tqdm_update(tqdm_self, n=1):
            result = original_update(tqdm_self, n)

            task = getattr(tqdm_self, task_attr_name, None)
            if not task:
                return result

            with progress_lock:
                try:
                    if tqdm_self.total and tqdm_self.total > 0:
                        progress = (tqdm_self.n / tqdm_self.total) * phase_range
                        total_progress = tqdm_self._phase_offset + progress
                        task.progress_percentage = min(90, max(10, int(total_progress)))

                        # Call custom callback to update model-specific fields
                        if progress_fields_callback:
                            progress_fields_callback(task, tqdm_self, tqdm_self._desc)

                        # Update current step with progress details
                        if tqdm_self._desc:
                            progress_text = f"{tqdm_self._desc} ({tqdm_self.n}"
                            if tqdm_self.total:
                                progress_text += f"/{tqdm_self.total}"
                            progress_text += ")"
                            task.current_step = progress_text

                        task.save()
                except Exception:
                    rollbar.report_exc_info(sys.exc_info())
                    logger.debug("Błąd aktualizacji postępu zadania", exc_info=True)

            return result

        return patched_tqdm_update

    def _create_patched_close(self):
        task_attr_name = self.task_attr_name
        phase_range = self.phase_range
        progress_lock = self.progress_lock
        original_close = self.original_close

        def patched_tqdm_close(tqdm_self):
            result = original_close(tqdm_self)

            task = getattr(tqdm_self, task_attr_name, None)
            if not task:
                return result

            with progress_lock:
                try:
                    if tqdm_self.total and tqdm_self.n >= tqdm_self.total:
                        total_progress = tqdm_self._phase_offset + phase_range
                        task.progress_percentage = min(90, int(total_progress))
                        task.save()
                except Exception:
                    rollbar.report_exc_info(sys.exc_info())
                    logger.debug(
                        "Błąd aktualizacji postępu zadania (close)", exc_info=True
                    )

            return result

        return patched_tqdm_close

    def apply(self, progress_fields_callback=None):
        """Apply the monkey patches to tqdm."""
        self.tqdm.tqdm.__init__ = self._create_patched_init()
        self.tqdm.tqdm.update = self._create_patched_update(progress_fields_callback)
        self.tqdm.tqdm.close = self._create_patched_close()

    def restore(self):
        """Restore original tqdm methods."""
        self.tqdm.tqdm.__init__ = self.original_init
        self.tqdm.tqdm.update = self.original_update
        self.tqdm.tqdm.close = self.original_close


@contextmanager
def tqdm_progress_context(
    task_record,
    task_attr_name,
    progress_fields_callback=None,
    phase_offset=10,
    phase_range=35,
):
    """
    Context manager for tqdm progress patching.
    Ensures proper cleanup of monkey patches.
    """
    patcher = TqdmProgressPatcher(
        task_record, task_attr_name, phase_offset, phase_range
    )
    patcher.apply(progress_fields_callback)
    try:
        yield patcher
    finally:
        patcher.restore()


def validate_pbn_user(user_id):
    """
    Validate that a user exists and has valid PBN credentials.

    Returns:
        tuple: (user, pbn_user) if valid

    Raises:
        ValueError: If user or credentials are invalid
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


def create_task_with_lock(task_model, user, initial_step):
    """
    Create a task record with atomic transaction to prevent race conditions.

    Returns:
        task_record: The created task record

    Raises:
        ValueError: If another task is already running
    """
    from django.db import transaction
    from django.utils import timezone

    with transaction.atomic():
        if task_model.objects.filter(status="running").exists():
            raise ValueError(
                "Another download task is already running. Please wait for it to complete."
            )

        return task_model.objects.create(
            user=user,
            status="running",
            started_at=timezone.now(),
            current_step=initial_step,
            progress_percentage=0,
        )


def mark_task_completed(task_record, final_step):
    """Mark a task as completed successfully."""
    from django.utils import timezone

    task_record.status = "completed"
    task_record.current_step = final_step
    task_record.progress_percentage = 100
    task_record.completed_at = timezone.now()
    task_record.save()


def mark_task_failed(task_record, error):
    """Mark a task as failed with error message."""
    from django.utils import timezone

    if task_record:
        task_record.status = "failed"
        task_record.error_message = str(error)
        task_record.completed_at = timezone.now()
        task_record.save()


@app.task
def download_institution_publications(user_id):
    """
    Download institution publications using PBN API management commands.
    Uses database-based locking to ensure only one instance runs at a time.

    Args:
        user_id: ID of the user initiating the download (must have valid PBN token)
    """
    from django.core.management import call_command

    from pbn_downloader_app.models import PbnDownloadTask

    # Check if there's already a running task
    running_task = PbnDownloadTask.objects.filter(status="running").first()
    if running_task:
        raise ValueError(
            "Another download task is already running. Please wait for it to complete."
        )

    task_record = None
    try:
        user, pbn_user = validate_pbn_user(user_id)
        task_record = create_task_with_lock(
            PbnDownloadTask, user, "Inicjalizacja pobierania..."
        )

        def update_publications_progress(task, tqdm_self, desc):
            """Update publication-specific progress fields."""
            if not desc:
                return
            if "publikacj" in desc.lower():
                task.publications_processed = tqdm_self.n
                if tqdm_self.total:
                    task.total_publications = tqdm_self.total
            elif "oświadczen" in desc.lower() or "statement" in desc.lower():
                task.statements_processed = tqdm_self.n
                if tqdm_self.total:
                    task.total_statements = tqdm_self.total

        # Phase 1: Download publications
        task_record.current_step = "Pobieranie publikacji instytucji (Faza 1/2)"
        task_record.progress_percentage = 10
        task_record.save()

        with tqdm_progress_context(
            task_record,
            "_task_record",
            update_publications_progress,
            phase_offset=10,
            phase_range=35,
        ):
            call_command(
                "pbn_pobierz_publikacje_z_instytucji_v2", user_token=pbn_user.pbn_token
            )

        # Phase 2: Download statements and publications
        task_record.current_step = "Pobieranie oświadczeń i publikacji (Faza 2/2)"
        task_record.progress_percentage = 50
        task_record.save()

        with tqdm_progress_context(
            task_record,
            "_task_record",
            update_publications_progress,
            phase_offset=50,
            phase_range=35,
        ):
            call_command(
                "pbn_pobierz_oswiadczenia_i_publikacje_v1",
                user_token=pbn_user.pbn_token,
            )

        task_record.current_step = "Finalizowanie pobierania..."
        task_record.progress_percentage = 90
        task_record.save()

        mark_task_completed(task_record, "Pobieranie zakończone pomyślnie")

    except Exception as e:
        mark_task_failed(task_record, e)
        raise


@app.task
def download_institution_people(user_id):
    """
    Download institution people using PBN API integrator function.
    Uses database-based locking to ensure only one instance runs at a time.

    Args:
        user_id: ID of the user initiating the download (must have valid PBN token)
    """
    from bpp.models import Uczelnia
    from pbn_downloader_app.models import PbnInstitutionPeopleTask

    # Check if there's already a running task
    running_task = PbnInstitutionPeopleTask.objects.filter(status="running").first()
    if running_task:
        raise ValueError(
            "Another people download task is already running. "
            "Please wait for it to complete."
        )

    task_record = None
    try:
        user, pbn_user = validate_pbn_user(user_id)

        # Get institution ID
        uczelnia = Uczelnia.objects.get_default()
        if not uczelnia.pbn_uid_id:
            raise ValueError(
                "Default institution does not have PBN UID. "
                "Please run PBN integration first."
            )

        task_record = create_task_with_lock(
            PbnInstitutionPeopleTask,
            user,
            "Inicjalizacja pobierania osób z instytucji...",
        )

        def update_people_progress(task, tqdm_self, desc):
            """Update people-specific progress fields."""
            task.people_processed = tqdm_self.n
            if tqdm_self.total:
                task.total_people = tqdm_self.total

        # Run the people download function
        task_record.current_step = "Pobieranie osób z instytucji z PBN"
        task_record.progress_percentage = 10
        task_record.save()

        with tqdm_progress_context(
            task_record,
            "_people_task_record",
            update_people_progress,
            phase_offset=10,
            phase_range=80,
        ):
            from pbn_integrator.utils import pobierz_ludzi_z_uczelni

            pobierz_ludzi_z_uczelni(pbn_user.pbn_token, uczelnia.pbn_uid_id)

        task_record.current_step = "Finalizowanie pobierania osób..."
        task_record.progress_percentage = 95
        task_record.save()

        mark_task_completed(task_record, "Pobieranie osób zakończone pomyślnie")

    except Exception as e:
        mark_task_failed(task_record, e)
        raise


def get_pbn_client(pbn_user):
    """
    Create a PBN client with proper configuration.

    Returns:
        tuple: (client, uczelnia) if successful

    Raises:
        ValueError: If configuration is invalid
    """
    from bpp.models import Uczelnia
    from pbn_api.client import PBNClient, RequestsTransport

    uczelnia = Uczelnia.objects.get_default()
    if not uczelnia:
        raise ValueError("No default institution configured")

    app_id = uczelnia.pbn_app_name
    app_token = uczelnia.pbn_app_token
    base_url = uczelnia.pbn_api_root

    if not all([app_id, app_token, base_url]):
        raise ValueError(
            "Institution PBN settings not properly configured "
            "(app_id, app_token, or base_url missing)"
        )

    transport = RequestsTransport(app_id, app_token, base_url, pbn_user.pbn_token)
    client = PBNClient(transport)

    return client, uczelnia


class JournalsProgressCallback:
    """Callback class for tracking journals download progress."""

    def __init__(self, task):
        self.task = task
        self.phase_offset = 10
        self.phase_range = 40  # 10-50% for download phase

    def update(self, current, total, label):
        if total and total > 0:
            progress = (current / total) * self.phase_range + self.phase_offset
            self.task.progress_percentage = min(50, max(10, int(progress)))
            self.task.journals_processed = current
            self.task.total_journals = total
            self.task.current_step = f"{label} ({current}/{total})"
            self.task.save()

    def clear(self):
        pass


@app.task
def download_journals(user_id):
    """
    Download journals from PBN API and integrate with BPP Zrodlo records.
    Uses database-based locking to ensure only one instance runs at a time.

    Args:
        user_id: ID of the user initiating the download (must have valid PBN token)
    """
    from bpp.models import Zrodlo
    from pbn_downloader_app.models import PbnJournalsDownloadTask

    # Check if there's already a running task
    running_task = PbnJournalsDownloadTask.objects.filter(status="running").first()
    if running_task:
        raise ValueError(
            "Another journals download task is already running. "
            "Please wait for it to complete."
        )

    task_record = None
    try:
        user, pbn_user = validate_pbn_user(user_id)
        client, _uczelnia = get_pbn_client(pbn_user)

        task_record = create_task_with_lock(
            PbnJournalsDownloadTask, user, "Inicjalizacja pobierania zrodel..."
        )

        callback = JournalsProgressCallback(task_record)

        # Phase 1: Download journals from PBN
        task_record.current_step = "Pobieranie zrodel z PBN (Faza 1/2)"
        task_record.progress_percentage = 10
        task_record.save()

        from pbn_integrator.utils import pobierz_zrodla_mnisw

        pobierz_zrodla_mnisw(client, callback=callback)

        task_record.progress_percentage = 50
        task_record.save()

        # Phase 2: Integration
        task_record.current_step = "Integracja zrodel z BPP (Faza 2/2)"
        task_record.progress_percentage = 55
        task_record.save()

        zrodla_without_pbn_before = Zrodlo.objects.filter(pbn_uid_id=None).count()

        from pbn_integrator.utils import integruj_zrodla

        integruj_zrodla(disable_progress_bar=True)

        zrodla_without_pbn_after = Zrodlo.objects.filter(pbn_uid_id=None).count()
        integrated_count = zrodla_without_pbn_before - zrodla_without_pbn_after

        task_record.zrodla_integrated = max(0, integrated_count)
        task_record.current_step = "Aktualizacja brakujących dyscyplin..."
        task_record.progress_percentage = 90
        task_record.save()

        # Zaktualizuj listę brakujących dyscyplin po pobraniu źródeł
        from pbn_komparator_zrodel.utils import aktualizuj_brakujace_dyscypliny_pbn

        aktualizuj_brakujace_dyscypliny_pbn()

        task_record.current_step = "Finalizowanie..."
        task_record.progress_percentage = 95
        task_record.save()

        mark_task_completed(task_record, "Pobieranie zrodel zakonczone pomyslnie")

    except Exception as e:
        mark_task_failed(task_record, e)
        raise
