# Create your models here.
from django.db import models

from .fields import LiczbaNField

from bpp.models.autor import Autor
from bpp.models.dyscyplina_naukowa import Dyscyplina_Naukowa
from bpp.models.uczelnia import Uczelnia


class LiczbaNDlaUczelni(models.Model):
    uczelnia = models.ForeignKey(Uczelnia, on_delete=models.CASCADE)
    dyscyplina_naukowa = models.ForeignKey(Dyscyplina_Naukowa, on_delete=models.CASCADE)
    liczba_n = LiczbaNField()

    class Meta:
        verbose_name = "Liczba N dla uczelni"
        verbose_name_plural = "Liczby N dla uczelni"
        unique_together = [
            ("uczelnia", "dyscyplina_naukowa"),
        ]


class LiczbaNDlaAutora(models.Model):
    autor = models.ForeignKey(Autor, on_delete=models.CASCADE)
    dyscyplina_naukowa = models.ForeignKey(Dyscyplina_Naukowa, on_delete=models.CASCADE)
    liczba_n = LiczbaNField()

    class Meta:
        verbose_name = "liczba N dla autora"
        verbose_name_plural = "liczby N dla autora"
        unique_together = [
            (
                "autor",
                "dyscyplina_naukowa",
            )
        ]
