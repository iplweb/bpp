from django.db import models

from django.contrib.auth import get_user_model

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
        max_length=255, blank=True, null=True, verbose_name="ID zadania Celery"
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

    class Meta:
        verbose_name = "Sesja importu"
        verbose_name_plural = "Sesje importu"
        ordering = ["-started_at"]

    def __str__(self):
        return f"Import {self.user} - {self.started_at:%Y-%m-%d %H:%M} - {self.get_status_display()}"

    def mark_completed(self):
        """Mark the session as completed"""
        self.status = "completed"
        self.completed_at = timezone.now()
        self.save()

    def mark_failed(self, error_message, traceback=""):
        """Mark the session as failed with error details"""
        self.status = "failed"
        self.error_message = error_message
        self.error_traceback = traceback
        self.completed_at = timezone.now()
        self.save()

    def update_progress(self, step_name, progress_percent, step_number=None):
        """Update current progress"""
        self.current_step = step_name
        self.current_step_progress = progress_percent
        if step_number:
            self.completed_steps = step_number
        self.save()

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


class ImportStep(models.Model):
    """Define import steps and their configuration"""

    name = models.CharField(max_length=100, unique=True, verbose_name="Nazwa")
    display_name = models.CharField(max_length=200, verbose_name="Nazwa wyświetlana")
    description = models.TextField(blank=True, verbose_name="Opis")
    order = models.IntegerField(default=0, verbose_name="Kolejność")
    is_optional = models.BooleanField(default=False, verbose_name="Opcjonalny")
    estimated_duration = models.IntegerField(
        default=60,
        help_text="Szacowany czas w sekundach",
        verbose_name="Szacowany czas trwania",
    )
    icon_class = models.CharField(
        max_length=50, default="fi-download", verbose_name="Klasa ikony"
    )

    class Meta:
        verbose_name = "Krok importu"
        verbose_name_plural = "Kroki importu"
        ordering = ["order"]

    def __str__(self):
        return self.display_name


class ImportStatistics(models.Model):
    """Track statistics for import sessions"""

    session = models.OneToOneField(
        ImportSession,
        on_delete=models.CASCADE,
        related_name="statistics",
        verbose_name="Sesja",
    )

    # Record counts
    institutions_imported = models.IntegerField(default=0)
    authors_imported = models.IntegerField(default=0)
    publications_imported = models.IntegerField(default=0)
    journals_imported = models.IntegerField(default=0)
    publishers_imported = models.IntegerField(default=0)
    conferences_imported = models.IntegerField(default=0)
    statements_imported = models.IntegerField(default=0)

    # Error counts
    institutions_failed = models.IntegerField(default=0)
    authors_failed = models.IntegerField(default=0)
    publications_failed = models.IntegerField(default=0)

    # Timing
    total_api_calls = models.IntegerField(default=0)
    total_api_time = models.FloatField(
        default=0.0, help_text="Total API time in seconds"
    )

    # Fun statistics
    coffee_breaks_recommended = models.IntegerField(default=0)
    motivational_messages_shown = models.IntegerField(default=0)

    class Meta:
        verbose_name = "Statystyki importu"
        verbose_name_plural = "Statystyki importu"

    def __str__(self):
        return f"Statystyki dla {self.session}"

    def calculate_coffee_breaks(self):
        """Calculate recommended coffee breaks based on duration"""
        duration_minutes = (
            self.session.duration.total_seconds() / 60 if self.session.duration else 0
        )
        # One coffee break every 30 minutes
        self.coffee_breaks_recommended = int(duration_minutes / 30)
        return self.coffee_breaks_recommended
