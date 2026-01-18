from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone

User = get_user_model()


class ImportSession(models.Model):
    """Track individual import sessions with their progress"""

    STATUS_CHOICES = [
        ("pending", "Oczekuje"),
        ("running", "W trakcie"),
        ("paused", "Wstrzymany"),
        ("completed", "Zakończony"),
        ("failed", "Błąd"),
        ("cancelled", "Anulowany"),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Użytkownik")
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="Rozpoczęto")
    completed_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Zakończono"
    )
    status = models.CharField(
        max_length=20, choices=STATUS_CHOICES, default="pending", verbose_name="Status"
    )
    task_id = models.CharField(
        max_length=255, blank=True, default="", verbose_name="ID zadania Celery"
    )
    current_step = models.CharField(
        max_length=100, blank=True, verbose_name="Aktualny krok"
    )
    current_step_progress = models.IntegerField(
        default=0, verbose_name="Postęp aktualnego kroku (%)"
    )
    total_steps = models.IntegerField(default=0, verbose_name="Liczba kroków")
    completed_steps = models.IntegerField(default=0, verbose_name="Ukończone kroki")

    # Store detailed progress data as JSON
    progress_data = models.JSONField(
        default=dict, blank=True, verbose_name="Dane postępu"
    )

    # Configuration for this import session
    config = models.JSONField(
        default=dict, blank=True, verbose_name="Konfiguracja importu"
    )

    # Error information if failed
    error_message = models.TextField(blank=True, verbose_name="Komunikat błędu")
    error_traceback = models.TextField(blank=True, verbose_name="Ślad stosu błędu")

    # Timestamp for detecting stale/lost tasks
    last_updated = models.DateTimeField(
        auto_now=True, verbose_name="Ostatnia aktualizacja"
    )

    class Meta:
        verbose_name = "Sesja importu"
        verbose_name_plural = "Sesje importu"
        ordering = ["-started_at"]
        indexes = [
            models.Index(fields=["status", "-started_at"]),
            models.Index(fields=["user", "status"]),
        ]

    def __str__(self):
        return f"Import {self.user} - {self.started_at:%Y-%m-%d %H:%M} - {self.get_status_display()}"

    def mark_completed(self):
        """Mark the session as completed"""
        self.status = "completed"
        self.completed_at = timezone.now()
        self.save(update_fields=["status", "completed_at"])

    def mark_failed(self, error_message, traceback=""):
        """Mark the session as failed with error details"""
        self.status = "failed"
        self.error_message = error_message
        self.error_traceback = traceback
        self.completed_at = timezone.now()
        self.save(
            update_fields=["status", "error_message", "error_traceback", "completed_at"]
        )

    def update_progress(self, step_name, progress_percent, step_number=None):
        """Update current progress"""
        self.current_step = step_name
        self.current_step_progress = progress_percent
        update_fields = ["current_step", "current_step_progress"]
        if step_number:
            self.completed_steps = step_number
            update_fields.append("completed_steps")
        self.save(update_fields=update_fields)

    @property
    def overall_progress(self):
        """Calculate overall progress percentage"""
        if self.total_steps == 0:
            return 0
        base_progress = (self.completed_steps / self.total_steps) * 100
        step_contribution = self.current_step_progress / self.total_steps
        return min(100, int(base_progress + step_contribution))

    @property
    def duration(self):
        """Calculate session duration"""
        if self.completed_at:
            return self.completed_at - self.started_at
        return timezone.now() - self.started_at

    def is_task_lost(self):
        """
        Sprawdza czy zadanie Celery jest utracone.

        Uwaga: Ta metoda sprawdza TYLKO czy zadanie zostało faktycznie anulowane
        w Celery (status REVOKED). Zadania które długo nie aktualizują bazy
        NIE są uznawane za utracone - mogą wykonywać długie operacje.

        Returns:
            tuple: (is_lost: bool, reason: str|None)
        """
        if self.status != "running":
            return False, None

        # Sprawdź status w Celery - tylko REVOKED oznacza faktyczne anulowanie
        if self.task_id:
            try:
                from celery.result import AsyncResult

                result = AsyncResult(self.task_id)

                # REVOKED oznacza że zadanie zostało anulowane zewnętrznie
                # (np. przez reset workera, revoke, itp.)
                if result.state == "REVOKED":
                    return True, "Zadanie w tle zostało anulowane zewnętrznie"

            except Exception:
                # Błąd połączenia z brokerem - nie możemy zweryfikować
                pass

        return False, None

    def auto_cancel_if_lost(self):
        """
        Sprawdza czy zadanie jest utracone i automatycznie anuluje sesję.

        Returns:
            bool: True jeśli sesja została anulowana
        """
        is_lost, reason = self.is_task_lost()

        if is_lost:
            self.status = "failed"
            self.error_message = f"Import automatycznie anulowany: {reason}"
            self.save(update_fields=["status", "error_message"])

            ImportLog.objects.create(
                session=self,
                level="warning",
                step="Auto-anulowanie",
                message=f"Sesja importu została automatycznie anulowana: {reason}",
                details={"task_id": self.task_id, "reason": reason},
            )

            return True

        return False


class ImportLog(models.Model):
    """Store detailed log entries for each import session"""

    LEVEL_CHOICES = [
        ("debug", "Debug"),
        ("info", "Informacja"),
        ("warning", "Ostrzeżenie"),
        ("error", "Błąd"),
        ("success", "Sukces"),
        ("critical", "Krytyczny"),
    ]

    session = models.ForeignKey(
        ImportSession,
        on_delete=models.CASCADE,
        related_name="logs",
        verbose_name="Sesja",
    )
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Czas")
    level = models.CharField(
        max_length=20, choices=LEVEL_CHOICES, default="info", verbose_name="Poziom"
    )
    step = models.CharField(max_length=100, verbose_name="Krok")
    message = models.TextField(verbose_name="Komunikat")
    details = models.JSONField(null=True, blank=True, verbose_name="Szczegóły")

    class Meta:
        verbose_name = "Wpis dziennika importu"
        verbose_name_plural = "Wpisy dziennika importu"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["session", "-timestamp"]),
            models.Index(fields=["level"]),
        ]

    def __str__(self):
        return f"[{self.timestamp:%H:%M:%S}] {self.get_level_display()}: {self.message[:50]}"


class ImportInconsistency(models.Model):
    """Track inconsistencies found during PBN statement integration"""

    INCONSISTENCY_TYPE_CHOICES = [
        ("author_not_found", "Autor nie znaleziony w publikacji"),
        ("author_auto_fixed", "Autor automatycznie poprawiony"),
        ("author_needs_manual_fix", "Wymaga ręcznej korekty"),
        ("no_override_without_disciplines", "Brak nadpisania - brak dyscyplin"),
        ("publication_not_found", "Brak publikacji w BPP"),
        ("author_not_in_bpp", "Brak autora w BPP"),
        ("duplicate_orcid", "Duplikat ORCID - wielu autorów z tym samym ORCID"),
        (
            "leftover_affiliation_data",
            "Pozostałe dane afiliacji po przetworzeniu autorów",
        ),
    ]

    session = models.ForeignKey(
        ImportSession,
        on_delete=models.CASCADE,
        related_name="inconsistencies",
        verbose_name="Sesja",
    )
    timestamp = models.DateTimeField(auto_now_add=True, verbose_name="Czas")
    inconsistency_type = models.CharField(
        max_length=50,
        choices=INCONSISTENCY_TYPE_CHOICES,
        verbose_name="Typ nieścisłości",
    )

    # PBN-side data
    pbn_publication_id = models.CharField(
        max_length=255, blank=True, verbose_name="ID publikacji PBN"
    )
    pbn_publication_title = models.TextField(
        blank=True, verbose_name="Tytuł publikacji PBN"
    )
    pbn_author_id = models.CharField(
        max_length=255, blank=True, verbose_name="ID autora PBN"
    )
    pbn_author_name = models.CharField(
        max_length=500, blank=True, verbose_name="Nazwa autora PBN"
    )
    pbn_discipline = models.CharField(
        max_length=255, blank=True, verbose_name="Dyscyplina PBN"
    )

    # BPP-side data
    bpp_publication_id = models.IntegerField(
        null=True, blank=True, verbose_name="ID publikacji BPP"
    )
    bpp_publication_content_type = models.ForeignKey(
        ContentType,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name="Typ publikacji BPP",
    )
    bpp_publication_title = models.TextField(
        blank=True, verbose_name="Tytuł publikacji BPP"
    )
    bpp_author_id = models.IntegerField(
        null=True, blank=True, verbose_name="ID autora BPP"
    )
    bpp_author_name = models.CharField(
        max_length=500, blank=True, verbose_name="Nazwa autora BPP"
    )

    # Description and action
    message = models.TextField(verbose_name="Opis problemu")
    action_taken = models.TextField(blank=True, verbose_name="Podjęte działanie")

    # Resolution tracking (for future use)
    resolved = models.BooleanField(default=False, verbose_name="Rozwiązano")
    resolved_at = models.DateTimeField(
        null=True, blank=True, verbose_name="Data rozwiązania"
    )

    class Meta:
        verbose_name = "Nieścisłość importu"
        verbose_name_plural = "Nieścisłości importu"
        ordering = ["-timestamp"]
        indexes = [
            models.Index(fields=["session", "-timestamp"]),
            models.Index(fields=["inconsistency_type"]),
            models.Index(fields=["resolved"]),
        ]

    def __str__(self):
        return (
            f"[{self.timestamp:%H:%M:%S}] "
            f"{self.get_inconsistency_type_display()}: {self.message[:50]}"
        )
