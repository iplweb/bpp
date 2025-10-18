from django.db import models

from django_bpp.settings.base import AUTH_USER_MODEL


class PrzeMapowanieZrodla(models.Model):
    """Historia przemapowania lub usunięcia źródła skasowanego w PBN."""

    TYP_PRZEMAPOWANIE = "przemapowanie"
    TYP_USUNIECIE = "usuniecie"

    TYP_OPERACJI_CHOICES = [
        (TYP_PRZEMAPOWANIE, "Przemapowanie"),
        (TYP_USUNIECIE, "Usunięcie"),
    ]

    typ_operacji = models.CharField(
        max_length=20,
        choices=TYP_OPERACJI_CHOICES,
        default=TYP_PRZEMAPOWANIE,
        verbose_name="Typ operacji",
    )

    zrodlo_skasowane_pbn_uid = models.ForeignKey(
        "pbn_api.Journal",
        on_delete=models.CASCADE,
        related_name="przemapowania_jako_stare",
        verbose_name="Źródło skasowane (Journal PBN)",
    )

    zrodlo_stare = models.ForeignKey(
        "bpp.Zrodlo",
        on_delete=models.SET_NULL,
        related_name="przemapowania_jako_stare",
        verbose_name="Źródło stare (BPP)",
        null=True,
        blank=True,
        help_text="Może być NULL jeśli źródło zostało usunięte",
    )

    zrodlo_nowe = models.ForeignKey(
        "bpp.Zrodlo",
        on_delete=models.SET_NULL,
        related_name="przemapowania_jako_nowe",
        verbose_name="Źródło nowe (BPP)",
        null=True,
        blank=True,
        help_text="Wypełnione tylko dla operacji typu 'przemapowanie'",
    )

    liczba_rekordow = models.PositiveIntegerField(
        verbose_name="Liczba przemapowanych rekordów", default=0
    )

    utworzono = models.DateTimeField(auto_now_add=True, verbose_name="Data utworzenia")

    utworzono_przez = models.ForeignKey(
        AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name="Utworzono przez",
    )

    rekordy_historia = models.JSONField(
        verbose_name="Historia przemapowanych rekordów",
        help_text="Lista przemapowanych rekordów z podstawowymi informacjami",
        default=list,
        blank=True,
    )

    class Meta:
        verbose_name = "Przemapowanie źródła"
        verbose_name_plural = "Przemapowania źródeł"
        ordering = ["-utworzono"]

    def __str__(self):
        data = self.utworzono.strftime("%Y-%m-%d") if self.utworzono else "brak daty"
        zrodlo_stare_str = str(self.zrodlo_stare) if self.zrodlo_stare else "[usunięte]"

        if self.typ_operacji == self.TYP_USUNIECIE:
            return f"Usunięcie: {zrodlo_stare_str} ({data})"

        zrodlo_nowe_str = str(self.zrodlo_nowe) if self.zrodlo_nowe else "[usunięte]"
        return f"Przemapowanie: {zrodlo_stare_str} → {zrodlo_nowe_str} ({data})"
