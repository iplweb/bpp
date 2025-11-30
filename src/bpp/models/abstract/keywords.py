"""
Modele abstrakcyjne związane ze słowami kluczowymi.
"""

from django.contrib.postgres.fields import ArrayField
from django.db import models
from taggit.managers import TaggableManager


class ModelZeSlowamiKluczowymi(models.Model):
    class Meta:
        abstract = True

    slowa_kluczowe = TaggableManager(
        "Słowa kluczowe -- język polski",
        help_text="Lista słów kluczowych -- język polski.",
        blank=True,
    )

    slowa_kluczowe_eng = ArrayField(
        base_field=models.CharField(max_length=255, blank=True),
        verbose_name="Słowa kluczowe -- język angielski",
        help_text="Lista słów kluczowych -- język angielski",
        null=True,
        blank=True,
    )
