from django.contrib.auth import get_user_model
from django.db import models

User = get_user_model()


class NotADuplicate(models.Model):
    """Oznacza parę źródeł jako 'to nie jest duplikat'"""

    zrodlo = models.ForeignKey(
        "bpp.Zrodlo", on_delete=models.CASCADE, related_name="not_duplicate_main"
    )
    duplikat = models.ForeignKey(
        "bpp.Zrodlo", on_delete=models.CASCADE, related_name="not_duplicate_duplicate"
    )
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="notaduplicate_zrodlo_set",
    )
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = [("zrodlo", "duplikat")]
        verbose_name = "oznaczenie 'to nie duplikat'"
        verbose_name_plural = "oznaczenia 'to nie duplikat'"
        ordering = ["-created_on"]

    def __str__(self):
        return f"{self.zrodlo} ≠ {self.duplikat}"


class IgnoredSource(models.Model):
    """Źródła wykluczone z procesu deduplikacji"""

    zrodlo = models.OneToOneField(
        "bpp.Zrodlo", on_delete=models.CASCADE, related_name="ignored_in_dedup"
    )
    reason = models.TextField(blank=True, help_text="Powód wykluczenia z deduplikacji")
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="ignoredsource_zrodlo_set",
    )
    created_on = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "źródło ignorowane w deduplikacji"
        verbose_name_plural = "źródła ignorowane w deduplikacji"
        ordering = ["-created_on"]

    def __str__(self):
        return f"Ignorowane: {self.zrodlo}"
