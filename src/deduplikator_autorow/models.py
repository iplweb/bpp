from django.db import models

from django.utils import timezone

from bpp.models.profile import BppUser


class NotADuplicate(models.Model):
    autor = models.OneToOneField(
        "bpp.Autor",
        db_index=True,
        help_text="Primary key of the Scientist record that is NOT a duplicate",
        on_delete=models.CASCADE,
    )
    created_on = models.DateTimeField("Created on", default=timezone.now)
    created_by = models.ForeignKey(
        BppUser,
        on_delete=models.CASCADE,
        verbose_name="Created by",
        help_text="User who marked this scientist as not a duplicate",
    )

    class Meta:
        verbose_name = "Not a duplicate"
        verbose_name_plural = "Not duplicates"
        ordering = ["-created_on"]

    def __str__(self):
        return f"Autor {self.autor} (not duplicate) - {self.created_by}"


class LogAutomatycznegoScalania(models.Model):
    main_scientist_id = models.CharField(
        "Main Scientist ID",
        max_length=255,
        db_index=True,
        help_text="Primary key of the main scientist record",
    )
    duplicate_scientist_id = models.CharField(
        "Duplicate Scientist ID",
        max_length=255,
        db_index=True,
        help_text="Primary key of the duplicate scientist record that was merged",
    )
    updated_publications = models.JSONField(
        "Updated Publications",
        help_text="JSON data containing information about publications that were updated during merge",
    )
    created_on = models.DateTimeField("Created on", default=timezone.now)
    created_by = models.ForeignKey(
        BppUser,
        on_delete=models.CASCADE,
        verbose_name="Created by",
        help_text="User who performed the automatic merge",
    )

    class Meta:
        verbose_name = "Log automatycznego scalania"
        verbose_name_plural = "Logi automatycznego scalania"
        ordering = ["-created_on"]

    def __str__(self):
        return f"Merge: {self.duplicate_scientist_id} -> {self.main_scientist_id} ({self.created_on})"
