from django.db import models

from bpp.models import NazwaISkrot


class Kierunek_Studiow(NazwaISkrot):
    wydzial = models.ForeignKey("bpp.Wydzial", on_delete=models.PROTECT)

    opis = models.TextField(blank=True, null=True)
    adnotacje = models.TextField(blank=True, null=True)

    class Meta:
        verbose_name = "kierunek studiów"
        verbose_name_plural = "kierunki studiów"
        ordering = ("nazwa",)
        app_label = "bpp"
