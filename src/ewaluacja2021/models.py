# Create your models here.
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
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


class IloscUdzialowDlaAutora(models.Model):
    autor = models.ForeignKey(Autor, on_delete=models.CASCADE)
    dyscyplina_naukowa = models.ForeignKey(Dyscyplina_Naukowa, on_delete=models.CASCADE)
    ilosc_udzialow = LiczbaNField(validators=[MaxValueValidator(4)])
    ilosc_udzialow_monografie = LiczbaNField()

    class Meta:
        verbose_name = "ilość udziałów dla autora"
        verbose_name_plural = "ilości udziałów dla autorów"
        unique_together = [
            (
                "autor",
                "dyscyplina_naukowa",
            )
        ]

    def clean(self):
        if (
            self.ilosc_udzialow is not None
            and self.ilosc_udzialow_monografie is not None
            and self.ilosc_udzialow_monografie > self.ilosc_udzialow
        ):
            raise ValidationError(
                "Ilość udziałów za monografie nie może przekraczać ilości udziałów"
            )
