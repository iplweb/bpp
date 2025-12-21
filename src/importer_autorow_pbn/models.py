from django.contrib.auth import get_user_model
from django.db import models

from bpp.models import Autor
from long_running.models import Operation
from pbn_api.models import Scientist

User = get_user_model()


class DoNotRemind(models.Model):
    """Model to track PBN Scientists that should be permanently ignored"""

    scientist = models.OneToOneField(
        Scientist,
        on_delete=models.CASCADE,
        verbose_name="Naukowiec PBN",
        related_name="do_not_remind",
    )
    ignored_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name="Data ignorowania",
    )
    ignored_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name="Ignorowany przez",
    )
    reason = models.TextField(
        blank=True,
        verbose_name="Powód ignorowania",
        help_text="Opcjonalny powód ignorowania tego naukowca",
    )

    class Meta:
        verbose_name = "Ignorowany naukowiec PBN"
        verbose_name_plural = "Ignorowani naukowcy PBN"
        ordering = ["-ignored_at"]

    def __str__(self):
        return f"{self.scientist} (ignorowany {self.ignored_at.strftime('%Y-%m-%d')})"


class CachedScientistMatch(models.Model):
    """Cache wyników matchowania naukowców PBN do autorów BPP"""

    scientist = models.OneToOneField(
        Scientist,
        on_delete=models.CASCADE,
        primary_key=True,
        verbose_name="Naukowiec PBN",
        related_name="cached_match",
    )
    matched_autor = models.ForeignKey(
        Autor,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        verbose_name="Dopasowany autor BPP",
        related_name="cached_scientist_matches",
    )
    computed_at = models.DateTimeField(
        auto_now=True,
        verbose_name="Data obliczenia",
    )

    class Meta:
        verbose_name = "Cache dopasowania naukowca PBN"
        verbose_name_plural = "Cache dopasowań naukowców PBN"
        indexes = [models.Index(fields=["computed_at"])]

    def __str__(self):
        if self.matched_autor:
            return f"{self.scientist} -> {self.matched_autor}"
        return f"{self.scientist} -> (brak dopasowania)"


class MatchCacheRebuildOperation(Operation):
    """Operacja przebudowy cache'u matchów naukowców PBN"""

    total_scientists = models.PositiveIntegerField(
        default=0,
        verbose_name="Łączna liczba naukowców",
    )
    processed_scientists = models.PositiveIntegerField(
        default=0,
        verbose_name="Przetworzonych naukowców",
    )
    matches_found = models.PositiveIntegerField(
        default=0,
        verbose_name="Znalezionych dopasowań",
    )

    class Meta:
        verbose_name = "Przebudowa cache'u importu autorów PBN"
        verbose_name_plural = "Przebudowy cache'u importu autorów PBN"

    def get_progress_percent(self):
        if self.total_scientists == 0:
            return 0
        return int(self.processed_scientists * 100 / self.total_scientists)

    def perform(self):
        """Logika przebudowy cache'u - wywoływana przez task_perform()"""
        from .core import rebuild_match_cache

        rebuild_match_cache(self)
