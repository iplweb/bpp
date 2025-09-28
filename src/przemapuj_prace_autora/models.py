from django.conf import settings
from django.db import models

from django.utils import timezone


class PrzemapoaniePracAutora(models.Model):
    """Model przechowujący historię przemapowań prac autorów między jednostkami"""

    autor = models.ForeignKey("bpp.Autor", on_delete=models.CASCADE)
    jednostka_z = models.ForeignKey(
        "bpp.Jednostka",
        on_delete=models.CASCADE,
        related_name="przemapowania_z",
        verbose_name="Jednostka źródłowa",
    )
    jednostka_do = models.ForeignKey(
        "bpp.Jednostka",
        on_delete=models.CASCADE,
        related_name="przemapowania_do",
        verbose_name="Jednostka docelowa",
    )
    liczba_prac_ciaglych = models.IntegerField(
        default=0, verbose_name="Liczba prac ciągłych"
    )
    liczba_prac_zwartych = models.IntegerField(
        default=0, verbose_name="Liczba prac zwartych"
    )
    utworzono = models.DateTimeField(
        default=timezone.now, verbose_name="Data przemapowania"
    )
    utworzono_przez = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Wykonane przez",
    )
    prace_ciagle_historia = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Historia prac ciągłych",
        help_text="Lista ID i tytułów przemapowanych prac ciągłych",
    )
    prace_zwarte_historia = models.JSONField(
        default=list,
        blank=True,
        verbose_name="Historia prac zwartych",
        help_text="Lista ID i tytułów przemapowanych prac zwartych",
    )

    class Meta:
        verbose_name = "Przemapowanie prac autora"
        verbose_name_plural = "Przemapowania prac autorów"
        ordering = ["-utworzono"]

    def __str__(self):
        utworzono = self.utworzono.strftime("%Y-%m-%d %H:%M")
        return (
            f"{self.autor} - z {self.jednostka_z} do {self.jednostka_do} ({utworzono})"
        )

    @property
    def liczba_prac(self):
        """Całkowita liczba przemapowanych prac"""
        return self.liczba_prac_ciaglych + self.liczba_prac_zwartych
