from django.core.management import call_command

from long_running.util import wait_for_object
from pbn_api.models.queue import SendStatus

from django_bpp.celery_tasks import app


@app.task
def task_sprobuj_wyslac_do_pbn(pk):
    from pbn_api.models import PBN_Export_Queue

    p = wait_for_object(PBN_Export_Queue, pk)
    res = p.send_to_pbn()

    match res:
        case SendStatus.RETRY_LATER:
            task_sprobuj_wyslac_do_pbn.apply_async(args=[pk], countdown=5 * 60)

        case SendStatus.RETRY_SOON:
            # np. 423 Locked
            task_sprobuj_wyslac_do_pbn.apply_async(args=[pk], countdown=60)

        case SendStatus.RETRY_MUCH_LATER:
            # PraceSerwisoweException
            task_sprobuj_wyslac_do_pbn.apply_async(args=[pk], countdown=60 * 60 * 3)

        case (
            SendStatus.FINISHED_ERROR
            | SendStatus.FINISHED_OKAY
            | SendStatus.RETRY_AFTER_USER_AUTHORISED
        ):
            return

        case _:
            raise NotImplementedError(
                f"Return status for background send to PBN not supported {res=}"
            )


@app.task
def kolejka_wyczysc_wpisy_bez_rekordow():
    from pbn_api.models import PBN_Export_Queue

    for elem in PBN_Export_Queue.objects.all():
        if not elem.check_if_record_still_exists():
            elem.delete()


@app.task
def kolejka_ponow_wysylke_prac_po_zalogowaniu(pk):
    from pbn_api.models import PBN_Export_Queue

    # Użytkownik o ID pk zalogował się.
    # Odśwież do wysyłki prace które były jego po zalogowaniu
    for elem in PBN_Export_Queue.objects.filter(
        retry_after_user_authorised=True, zamowil_id=pk, wysylke_zakonczono=None
    ):
        task_sprobuj_wyslac_do_pbn.delay(elem.pk)

    # ... ale i odświez prace wszystkich użytkowników, którzy mają jego konto
    # jako konto do wysyłki:
    for elem in PBN_Export_Queue.objects.filter(
        retry_after_user_authorised=True,
        zamowil__przedstawiaj_w_pbn_jako_id=pk,
        wysylke_zakonczono=None,
    ):
        task_sprobuj_wyslac_do_pbn.delay(elem.pk)


@app.task
def download_institution_publications(user_id):
    """
    Download institution publications using PBN API management commands.
    Uses database-based locking to ensure only one instance runs at a time.

    Args:
        user_id: ID of the user initiating the download (must have valid PBN token)
    """
    from django.db import transaction

    from komparator_pbn.models import PbnDownloadTask

    from django.utils import timezone

    from bpp.models.profile import BppUser

    # Check if there's already a running task
    running_task = PbnDownloadTask.objects.filter(status="running").first()
    if running_task:
        raise ValueError(
            "Another download task is already running. Please wait for it to complete."
        )

    task_record = None
    try:
        user = BppUser.objects.get(pk=user_id)
        pbn_user = user.get_pbn_user()

        if not pbn_user.pbn_token:
            raise ValueError(
                f"User {user.username} is not authorized in PBN (no pbn_token)"
            )

        if not pbn_user.pbn_token_possibly_valid():
            raise ValueError(
                f"User {user.username} has an invalid or expired PBN token"
            )

        # Create task record with atomic transaction to prevent race conditions
        with transaction.atomic():
            # Double-check there's no running task within the transaction
            if PbnDownloadTask.objects.filter(status="running").exists():
                raise ValueError(
                    "Another download task is already running. Please wait for it to complete."
                )

            task_record = PbnDownloadTask.objects.create(
                user=user,
                status="running",
                started_at=timezone.now(),
                current_step="Inicjalizacja pobierania...",
                progress_percentage=0,
            )

        # Monkey-patch tqdm to capture progress and save to database
        from threading import Lock

        import tqdm

        original_tqdm_init = tqdm.tqdm.__init__
        original_tqdm_update = tqdm.tqdm.update
        original_tqdm_close = tqdm.tqdm.close
        progress_lock = Lock()

        def patched_tqdm_init(
            self, iterable=None, desc=None, total=None, *args, **kwargs
        ):
            # Store task record reference for progress updates
            self._task_record = task_record
            self._desc = desc or ""
            # Determine phase offset based on current step
            if task_record.current_step and "Faza 1" in task_record.current_step:
                self._phase_offset = 10  # First command: 10-45%
            elif task_record.current_step and "Faza 2" in task_record.current_step:
                self._phase_offset = 50  # Second command: 50-85%
            else:
                self._phase_offset = 10  # Default

            # Call original init
            original_tqdm_init(self, iterable, desc, total, *args, **kwargs)

        def patched_tqdm_update(self, n=1):
            result = original_tqdm_update(self, n)

            # Update database progress
            if hasattr(self, "_task_record") and self._task_record:
                with progress_lock:
                    try:
                        # Calculate progress percentage (10-45% for first command, 50-85% for second)
                        if self.total and self.total > 0:
                            command_progress = (
                                self.n / self.total
                            ) * 35  # Each command gets 35% of total progress
                            total_progress = self._phase_offset + command_progress

                            self._task_record.progress_percentage = min(
                                90, max(10, int(total_progress))
                            )

                            # Update current step with more detail
                            if self._desc:
                                if "publikacj" in self._desc.lower():
                                    self._task_record.publications_processed = self.n
                                    if self.total:
                                        self._task_record.total_publications = (
                                            self.total
                                        )
                                elif (
                                    "oświadczen" in self._desc.lower()
                                    or "statement" in self._desc.lower()
                                ):
                                    self._task_record.statements_processed = self.n
                                    if self.total:
                                        self._task_record.total_statements = self.total

                                # Update current step with progress details
                                progress_text = f"{self._desc} ({self.n}"
                                if self.total:
                                    progress_text += f"/{self.total}"
                                progress_text += ")"
                                self._task_record.current_step = progress_text

                            self._task_record.save()
                    except Exception:
                        pass  # Don't let database errors break the download

            return result

        def patched_tqdm_close(self):
            result = original_tqdm_close(self)

            # Final update when tqdm closes
            if hasattr(self, "_task_record") and self._task_record:
                with progress_lock:
                    try:
                        if self.total and self.n >= self.total:
                            # Command completed, update to end of phase
                            total_progress = self._phase_offset + 35
                            self._task_record.progress_percentage = min(
                                90, int(total_progress)
                            )
                            self._task_record.save()
                    except Exception:
                        pass

            return result

        # Apply monkey patches
        tqdm.tqdm.__init__ = patched_tqdm_init
        tqdm.tqdm.update = patched_tqdm_update
        tqdm.tqdm.close = patched_tqdm_close

        try:
            # Run the management commands with progress reporting
            task_record.current_step = "Pobieranie publikacji instytucji (Faza 1/2)"
            task_record.progress_percentage = 10
            task_record.save()

            call_command(
                "pbn_pobierz_publikacje_z_instytucji_v2", user_token=pbn_user.pbn_token
            )

            task_record.current_step = "Pobieranie oświadczeń i publikacji (Faza 2/2)"
            task_record.progress_percentage = 50
            task_record.save()

            call_command(
                "pbn_pobierz_oswiadczenia_i_publikacje_v1",
                user_token=pbn_user.pbn_token,
            )

            task_record.current_step = "Finalizowanie pobierania..."
            task_record.progress_percentage = 90
            task_record.save()

        finally:
            # Restore original tqdm methods
            tqdm.tqdm.__init__ = original_tqdm_init
            tqdm.tqdm.update = original_tqdm_update
            tqdm.tqdm.close = original_tqdm_close

        # Mark as completed
        task_record.status = "completed"
        task_record.current_step = "Pobieranie zakończone pomyślnie"
        task_record.progress_percentage = 100
        task_record.completed_at = timezone.now()
        task_record.save()

    except Exception as e:
        # Record the error
        if task_record:
            task_record.status = "failed"
            task_record.error_message = str(e)
            task_record.completed_at = timezone.now()
            task_record.save()
        raise
