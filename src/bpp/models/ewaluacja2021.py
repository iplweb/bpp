from django.db import models

from .dyscyplina_naukowa import Dyscyplina_Naukowa
from .uczelnia import Uczelnia


class Ewaluacja2021LiczbaNDlaUczelni(models.Model):
    uczelnia = models.ForeignKey(Uczelnia, on_delete=models.CASCADE)
    dyscyplina_naukowa = models.ForeignKey(Dyscyplina_Naukowa, on_delete=models.CASCADE)
    liczba_n = models.DecimalField(max_digits=9, decimal_places=4)

    class Meta:
        verbose_name = "Liczba N dla uczelni"
        verbose_name_plural = "Liczby N dla uczelni"
        unique_together = [
            ("uczelnia", "dyscyplina_naukowa"),
        ]
