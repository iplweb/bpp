import logging

from django.contrib.contenttypes.fields import GenericForeignKey
from django.db import models

from bpp.util import zaloguj_polkniety_wyjatek

logger = logging.getLogger(__name__)


class IgnorujRozbieznoscIf(models.Model):
    object = GenericForeignKey()

    content_type = models.ForeignKey(
        "contenttypes.ContentType", on_delete=models.CASCADE
    )
    object_id = models.PositiveIntegerField("Rekord", db_index=True)
    created_on = models.DateTimeField("Utworzono", auto_now_add=True)

    class Meta:
        verbose_name = "ignorowanie rozbieżności impact factor"
        verbose_name = "ignorowanie rozbieżności impact factor"

    def __str__(self):
        try:
            return f"Ignoruj rozbieżności punktacji IF dla rekordu {self.object}"
        except Exception:
            zaloguj_polkniety_wyjatek(
                f"Tworzenie reprezentacji tekstowej IgnorujRozbieznoscIf "
                f"(content_type_id={self.content_type_id}, "
                f"object_id={self.object_id})",
                logger=logger,
            )
            return 'Ignoruj rozbieżności punktacji IF dla rekordu "[brak rekordu, został usunięty]"'


class RozbieznosciIfLog(models.Model):
    """Log of IF updates from rozbieznosci_if view."""

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
    if_before = models.DecimalField(
        "IF przed zmianą",
        max_digits=6,
        decimal_places=3,
        null=True,
    )
    if_after = models.DecimalField(
        "IF po zmianie",
        max_digits=6,
        decimal_places=3,
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
        verbose_name = "log zmiany IF"
        verbose_name_plural = "logi zmian IF"
        ordering = ["-created_on"]

    def __str__(self):
        return f"Zmiana IF: {self.rekord} ({self.if_before} -> {self.if_after})"
