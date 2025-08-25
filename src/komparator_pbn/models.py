from django.conf import settings
from django.db import models


class PbnDownloadTask(models.Model):
    STATUS_CHOICES = [
        ("running", "Running"),
        ("completed", "Completed"),
        ("failed", "Failed"),
    ]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default="running")
    started_at = models.DateTimeField(auto_now_add=True)
    completed_at = models.DateTimeField(null=True, blank=True)
    error_message = models.TextField(null=True, blank=True)

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

    def __str__(self):
        return f"PBN Download Task {self.id} - {self.status}"

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
        from datetime import timedelta

        from django.utils import timezone

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
