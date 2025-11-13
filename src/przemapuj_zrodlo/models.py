from django.db import models

from django_bpp.settings.base import AUTH_USER_MODEL


class PrzemapowaZrodla(models.Model):
    """Historia przemapowania publikacji z jednego źródła do drugiego."""

    zrodlo_z = models.ForeignKey(
        "bpp.Zrodlo",
        on_delete=models.CASCADE,
        related_name="przemapowania_lokalne_z",
        verbose_name="Źródło źródłowe",
        help_text="Źródło, z którego przemapowano publikacje",
    )

    zrodlo_do = models.ForeignKey(
        "bpp.Zrodlo",
        on_delete=models.CASCADE,
        related_name="przemapowania_lokalne_do",
        verbose_name="Źródło docelowe",
        help_text="Źródło, do którego przemapowano publikacje",
    )

    liczba_publikacji = models.PositiveIntegerField(
        verbose_name="Liczba przemapowanych publikacji", default=0
    )

    publikacje_historia = models.JSONField(
        verbose_name="Historia przemapowanych publikacji",
        help_text="Lista przemapowanych publikacji z podstawowymi informacjami (ID, tytuł, rok)",
        default=list,
        blank=True,
    )

    utworzono = models.DateTimeField(auto_now_add=True, verbose_name="Data utworzenia")

    utworzono_przez = models.ForeignKey(
        AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="przemapowania_zrodla_utworzono",
        verbose_name="Utworzono przez",
    )

    cofnieto = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Data cofnięcia",
        help_text="Wypełnione jeśli przemapowanie zostało cofnięte",
    )

    cofnieto_przez = models.ForeignKey(
        AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="przemapowania_zrodla_cofnieto",
        verbose_name="Cofnięto przez",
    )

    class Meta:
        verbose_name = "Przemapowanie źródła"
        verbose_name_plural = "Przemapowania źródeł"
        ordering = ["-utworzono"]
        indexes = [
            models.Index(fields=["zrodlo_z"]),
            models.Index(fields=["zrodlo_do"]),
            models.Index(fields=["utworzono"]),
        ]

    def __str__(self):
        data = self.utworzono.strftime("%Y-%m-%d %H:%M") if self.utworzono else "?"
        zrodlo_z_str = str(self.zrodlo_z) if self.zrodlo_z else "[usunięte]"
        zrodlo_do_str = str(self.zrodlo_do) if self.zrodlo_do else "[usunięte]"

        status = ""
        if self.cofnieto:
            status = " [COFNIĘTE]"

        return f"{zrodlo_z_str} → {zrodlo_do_str} ({self.liczba_publikacji} pub., {data}){status}"

    @property
    def jest_cofniete(self):
        """Czy przemapowanie zostało cofnięte."""
        return self.cofnieto is not None

    @property
    def mozna_cofnac(self):
        """Czy przemapowanie można cofnąć (nie zostało jeszcze cofnięte)."""
        return not self.jest_cofniete
