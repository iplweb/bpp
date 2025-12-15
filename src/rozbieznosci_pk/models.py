from django.contrib.contenttypes.fields import GenericForeignKey
from django.db import models


class IgnorujRozbieznoscPk(models.Model):
    object = GenericForeignKey()

    content_type = models.ForeignKey(
        "contenttypes.ContentType", on_delete=models.CASCADE
    )
    object_id = models.PositiveIntegerField("Rekord", db_index=True)
    created_on = models.DateTimeField("Utworzono", auto_now_add=True)

    class Meta:
        verbose_name = "ignorowanie rozbieżności punktów MNiSW"
        verbose_name_plural = "ignorowanie rozbieżności punktów MNiSW"

    def __str__(self):
        try:
            return f"Ignoruj rozbieżności punktacji MNiSW dla rekordu {self.object}"
        except BaseException:
            return (
                'Ignoruj rozbieżności punktacji MNiSW dla rekordu "[brak rekordu, '
                'został usunięty]"'
            )


class RozbieznosciPkLog(models.Model):
    """Log of punkty_kbn updates from rozbieznosci_pk view."""

    rekord = models.ForeignKey(
        "bpp.Wydawnictwo_Ciagle",
        on_delete=models.CASCADE,
        verbose_name="Rekord",
    )
    zrodlo = models.ForeignKey(
        "bpp.Zrodlo",
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Źródło",
    )
    pk_before = models.DecimalField(
        "Punkty MNiSW przed zmianą",
        max_digits=6,
        decimal_places=2,
        null=True,
    )
    pk_after = models.DecimalField(
        "Punkty MNiSW po zmianie",
        max_digits=6,
        decimal_places=2,
        null=True,
    )
    user = models.ForeignKey(
        "bpp.BppUser",
        on_delete=models.SET_NULL,
        null=True,
        verbose_name="Użytkownik",
    )
    created_on = models.DateTimeField("Kiedy", auto_now_add=True)

    class Meta:
        verbose_name = "log zmiany punktów MNiSW"
        verbose_name_plural = "logi zmian punktów MNiSW"
        ordering = ["-created_on"]

    def __str__(self):
        return (
            f"Zmiana punktów MNiSW: {self.rekord} ({self.pk_before} -> {self.pk_after})"
        )
