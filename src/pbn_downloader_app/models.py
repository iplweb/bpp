from datetime import timedelta

from django.conf import settings
from django.db import models
from django.utils import timezone


class PbnTaskMixin:
    """Mixin providing common methods for PBN download task models."""

    def is_outdated(self, days=7):
        """Sprawdz czy pobranie jest przestarzale (starsze niz podana liczba dni)."""
        if self.status != "completed" or not self.completed_at:
            return False
        return self.completed_at < timezone.now() - timedelta(days=days)

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
                error_message="Task marked as failed due to stale status (process likely crashed)",
                completed_at=timezone.now(),
            )

        return count


class PbnDownloadTask(PbnTaskMixin, models.Model):
    """Track background download tasks from PBN API."""

    STATUS_CHOICES = [
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pbn_downloader_tasks",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="running")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")

    # Progress tracking fields
    current_step = models.CharField(max_length=200, blank=True, default="")
    progress_percentage = models.IntegerField(default=0)
    publications_processed = models.IntegerField(default=0)
    statements_processed = models.IntegerField(default=0)
    total_publications = models.IntegerField(null=True, blank=True)
    total_statements = models.IntegerField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-started_at"]
        verbose_name = "PBN Download Task"
        verbose_name_plural = "PBN Download Tasks"

    def __str__(self):
        return f"PBN Download Task {self.id} - {self.status}"


class PbnInstitutionPeopleTask(PbnTaskMixin, models.Model):
    """Track background download tasks for institution people from PBN API."""

    STATUS_CHOICES = [
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pbn_people_tasks",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="running")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")

    # Progress tracking fields
    current_step = models.CharField(max_length=200, blank=True, default="")
    progress_percentage = models.IntegerField(default=0)
    people_processed = models.IntegerField(default=0)
    total_people = models.IntegerField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-started_at"]
        verbose_name = "PBN Institution People Download Task"
        verbose_name_plural = "PBN Institution People Download Tasks"

    def __str__(self):
        return f"PBN People Download Task {self.id} - {self.status}"


class PbnJournalsDownloadTask(PbnTaskMixin, models.Model):
    """Track background download tasks for journals (sources) from PBN API."""

    STATUS_CHOICES = [
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="pbn_journals_tasks",
    )
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="running")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(blank=True, default="")

    # Progress tracking fields
    current_step = models.CharField(max_length=200, blank=True, default="")
    progress_percentage = models.IntegerField(default=0)
    journals_processed = models.IntegerField(default=0)
    total_journals = models.IntegerField(null=True, blank=True)
    zrodla_integrated = models.IntegerField(default=0)
    last_updated = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-started_at"]
        verbose_name = "PBN Journals Download Task"
        verbose_name_plural = "PBN Journals Download Tasks"

    def __str__(self):
        return f"PBN Journals Download Task {self.id} - {self.status}"
