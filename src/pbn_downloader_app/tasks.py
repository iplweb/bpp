from django.core.management import call_command

from django_bpp.celery_tasks import app


@app.task
def download_institution_publications(user_id):
    """
    Download institution publications using PBN API management commands.
    Uses database-based locking to ensure only one instance runs at a time.

    Args:
        user_id: ID of the user initiating the download (must have valid PBN token)
    """
    from django.db import transaction

    from pbn_downloader_app.models import PbnDownloadTask

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


@app.task
def download_institution_people(user_id):
    """
    Download institution people using PBN API integrator function.
    Uses database-based locking to ensure only one instance runs at a time.

    Args:
        user_id: ID of the user initiating the download (must have valid PBN token)
    """
    from django.db import transaction

    from pbn_downloader_app.models import PbnInstitutionPeopleTask

    from django.utils import timezone

    from bpp.models import Uczelnia
    from bpp.models.profile import BppUser

    # Check if there's already a running task
    running_task = PbnInstitutionPeopleTask.objects.filter(status="running").first()
    if running_task:
        raise ValueError(
            "Another people download task is already running. Please wait for it to complete."
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

        # Get institution ID
        uczelnia = Uczelnia.objects.get_default()
        if not uczelnia.pbn_uid_id:
            raise ValueError(
                "Default institution does not have PBN UID. Please run PBN integration first."
            )

        # Create task record with atomic transaction to prevent race conditions
        with transaction.atomic():
            # Double-check there's no running task within the transaction
            if PbnInstitutionPeopleTask.objects.filter(status="running").exists():
                raise ValueError(
                    "Another people download task is already running. Please wait for it to complete."
                )

            task_record = PbnInstitutionPeopleTask.objects.create(
                user=user,
                status="running",
                started_at=timezone.now(),
                current_step="Inicjalizacja pobierania osób z instytucji...",
                progress_percentage=0,
            )

        # Create PBN client
        from pbn_api.client import PBNClient

        client = PBNClient(pbn_user.pbn_token)

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
            self._people_task_record = task_record
            self._desc = desc or ""
            # Call original init
            original_tqdm_init(self, iterable, desc, total, *args, **kwargs)

        def patched_tqdm_update(self, n=1):
            result = original_tqdm_update(self, n)

            # Update database progress
            if hasattr(self, "_people_task_record") and self._people_task_record:
                with progress_lock:
                    try:
                        # Calculate progress percentage (10-90%)
                        if self.total and self.total > 0:
                            progress = (self.n / self.total) * 80 + 10  # 10-90%
                            total_progress = min(90, max(10, int(progress)))

                            self._people_task_record.progress_percentage = (
                                total_progress
                            )
                            self._people_task_record.people_processed = self.n
                            if self.total:
                                self._people_task_record.total_people = self.total

                            # Update current step with progress details
                            if self._desc:
                                progress_text = f"{self._desc} ({self.n}"
                                if self.total:
                                    progress_text += f"/{self.total}"
                                progress_text += ")"
                                self._people_task_record.current_step = progress_text

                            self._people_task_record.save()
                    except Exception:
                        pass  # Don't let database errors break the download

            return result

        def patched_tqdm_close(self):
            result = original_tqdm_close(self)

            # Final update when tqdm closes
            if hasattr(self, "_people_task_record") and self._people_task_record:
                with progress_lock:
                    try:
                        if self.total and self.n >= self.total:
                            # Task completed
                            self._people_task_record.progress_percentage = 90
                            self._people_task_record.save()
                    except Exception:
                        pass

            return result

        # Apply monkey patches
        tqdm.tqdm.__init__ = patched_tqdm_init
        tqdm.tqdm.update = patched_tqdm_update
        tqdm.tqdm.close = patched_tqdm_close

        try:
            # Run the people download function
            task_record.current_step = "Pobieranie osób z instytucji z PBN"
            task_record.progress_percentage = 10
            task_record.save()

            from pbn_api.integrator import pobierz_ludzi_z_uczelni

            pobierz_ludzi_z_uczelni(client, uczelnia.pbn_uid_id)

            task_record.current_step = "Finalizowanie pobierania osób..."
            task_record.progress_percentage = 95
            task_record.save()

        finally:
            # Restore original tqdm methods
            tqdm.tqdm.__init__ = original_tqdm_init
            tqdm.tqdm.update = original_tqdm_update
            tqdm.tqdm.close = original_tqdm_close

        # Mark as completed
        task_record.status = "completed"
        task_record.current_step = "Pobieranie osób zakończone pomyślnie"
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
