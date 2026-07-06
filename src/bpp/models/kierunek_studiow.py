from django.db import models

from bpp.models import NazwaISkrot


class Kierunek_Studiow(NazwaISkrot):
    wydzial = models.ForeignKey("bpp.Jednostka", on_delete=models.PROTECT)

    # legacy null=True (jest tak na produkcji); usunięcie wymagałoby migracji
    # + obsługi istniejących NULL — poza zakresem sprzątania lintu.
    opis = models.TextField(blank=True, null=True)  # noqa: DJ001
    adnotacje = models.TextField(blank=True, null=True)  # noqa: DJ001

    class Meta:
        verbose_name = "kierunek studiów"
        verbose_name_plural = "kierunki studiów"
        ordering = ("nazwa",)
        app_label = "bpp"
