from datetime import timedelta

from django.conf import settings
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.utils import timezone


class PbnWysylkaOswiadczenTask(models.Model):
    """Track background tasks for sending statements to PBN API."""

    STATUS_CHOICES = [
        ("pending", "Oczekuje"),
        ("running", "W trakcie"),
        ("completed", "Zakonczone"),
        ("failed", "Blad"),
        ("maintenance", "Prace serwisowe PBN"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pbn_wysylka_tasks",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="pending")

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    # Progress tracking
    total_publications = models.IntegerField(default=0)
    processed_publications = models.IntegerField(default=0)
    current_publication = models.CharField(max_length=300, blank=True, default="")

    # Counters
    success_count = models.IntegerField(default=0)
    error_count = models.IntegerField(default=0)
    skipped_count = models.IntegerField(default=0)
    synchronized_count = models.IntegerField(default=0)

    # Parameters
    rok_od = models.IntegerField(default=2022)
    rok_do = models.IntegerField(default=2025)
    tytul = models.CharField(
        max_length=500, blank=True, default="", help_text="Filtr tytulu (zawiera)"
    )
    resume_mode = models.BooleanField(
        default=False, help_text="True = kontynuuj, False = od nowa"
    )

    # Error and task tracking
    error_message = models.TextField(blank=True, default="")
    celery_task_id = models.CharField(max_length=255, blank=True, default="")

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Zadanie wysylki oswiadczen"
        verbose_name_plural = "Zadania wysylki oswiadczen"

    def __str__(self):
        return f"Wysyłka oświadczeń {self.pk} ({self.status}) - {self.created_at}"

    @property
    def progress_percent(self):
        if self.total_publications == 0:
            return 0
        return int((self.processed_publications / self.total_publications) * 100)

    def is_stalled(self, minutes=15):
        """Check if a running task has stalled (no updates for X minutes)."""
        if self.status != "running":
            return False
        return self.last_updated < timezone.now() - timedelta(minutes=minutes)

    @classmethod
    def get_latest_task(cls):
        """Get the most recent task or None if no tasks exist."""
        return cls.objects.first()

    @classmethod
    def cleanup_stale_running_tasks(cls, max_age_hours=24):
        """
        Clean up stale 'running' tasks that have been running for too long.
        This helps recover from crashed processes that didn't update task status.
        """
        cutoff_time = timezone.now() - timedelta(hours=max_age_hours)
        stale_tasks = cls.objects.filter(status="running", started_at__lt=cutoff_time)

        count = stale_tasks.count()
        if count > 0:
            stale_tasks.update(
                status="failed",
                error_message="Zadanie oznaczone jako nieudane z powodu przestarzalego "
                "statusu (proces prawdopodobnie sie zakonczyl)",
                completed_at=timezone.now(),
            )

        return count


class PbnWysylkaLog(models.Model):
    """Log entry for each publication processed during statement sending."""

    STATUS_CHOICES = [
        ("success", "Sukces"),
        ("error", "Blad"),
        ("skipped", "Pominieto"),
        ("synchronized", "Zsynchronizowana"),
        ("maintenance", "Prace serwisowe PBN"),
    ]

    task = models.ForeignKey(
        PbnWysylkaOswiadczenTask,
        on_delete=models.CASCADE,
        related_name="logs",
    )

    # Publication reference using GenericForeignKey
    content_type = models.ForeignKey(
        ContentType,
        on_delete=models.CASCADE,
        limit_choices_to={
            "app_label": "bpp",
            "model__in": ["wydawnictwo_ciagle", "wydawnictwo_zwarte"],
        },
    )
    object_id = models.PositiveIntegerField()
    publication = GenericForeignKey("content_type", "object_id")

    # PBN UID for reference (stored separately for easier querying)
    pbn_uid = models.CharField(max_length=100, db_index=True)

    status = models.CharField(max_length=20, choices=STATUS_CHOICES, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)

    # JSON data sent/received
    json_sent = models.JSONField(null=True, blank=True)
    json_response = models.JSONField(null=True, blank=True)

    # Error details
    error_message = models.TextField(blank=True, default="")
    retry_count = models.IntegerField(default=0)

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Log wysylki"
        verbose_name_plural = "Logi wysylki"
        indexes = [
            models.Index(fields=["task", "status"]),
            models.Index(fields=["content_type", "object_id"]),
        ]

    def __str__(self):
        return f"Log {self.pk}: {self.status} - {self.pbn_uid}"
