from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import models

from .fields import LiczbaNField

from bpp.fields import YearField
from bpp.models.autor import Autor
from bpp.models.dyscyplina_naukowa import Dyscyplina_Naukowa
from bpp.models.uczelnia import Uczelnia


class BazaLiczbyNDlaUczelni(models.Model):
    uczelnia = models.ForeignKey(Uczelnia, on_delete=models.CASCADE)
    dyscyplina_naukowa = models.ForeignKey(Dyscyplina_Naukowa, on_delete=models.CASCADE)
    liczba_n = LiczbaNField()

    class Meta:
        abstract = True

    def __str__(self):
        return f"{self.dyscyplina_naukowa.nazwa} -> {self.liczba_n}"


class LiczbaNDlaUczelni_2022_2025(BazaLiczbyNDlaUczelni):
    class Meta:
        verbose_name = "Liczba N dla uczelni 2022-2025"
        verbose_name_plural = "Liczby N dla uczelni 2022-2025"
        unique_together = [
            ("uczelnia", "dyscyplina_naukowa"),
        ]


class BazaIlosciUdzialowDlaAutora(models.Model):
    autor = models.ForeignKey(Autor, on_delete=models.CASCADE)
    dyscyplina_naukowa = models.ForeignKey(Dyscyplina_Naukowa, on_delete=models.CASCADE)
    ilosc_udzialow = LiczbaNField(validators=[MaxValueValidator(4)])
    ilosc_udzialow_monografie = LiczbaNField()

    class Meta:
        abstract = True

    def clean(self):
        if (
            self.ilosc_udzialow is not None
            and self.ilosc_udzialow_monografie is not None
            and self.ilosc_udzialow_monografie > self.ilosc_udzialow
        ):
            raise ValidationError(
                "Ilość udziałów za monografie nie może przekraczać ilości udziałów"
            )


class IloscUdzialowDlaAutora_2022_2025(BazaIlosciUdzialowDlaAutora):
    class Meta:
        verbose_name = "ilość udziałów dla autora 2022-2025"
        verbose_name_plural = "ilości udziałów dla autorów 2022-2025"
        unique_together = [
            (
                "autor",
                "dyscyplina_naukowa",
            )
        ]


class IloscUdzialowDlaAutoraZaRok(BazaIlosciUdzialowDlaAutora):
    rok = YearField()

    class Meta:
        verbose_name = "ilość udziałów dla autora za rok"
        verbose_name_plural = "ilości udziałów dla autorów za lata"
        unique_together = [("autor", "dyscyplina_naukowa", "rok")]


class DyscyplinaNieRaportowana_2022_2025(models.Model):
    uczelnia = models.ForeignKey("bpp.Uczelnia", on_delete=models.CASCADE)
    dyscyplina_naukowa = models.ForeignKey(
        "bpp.Dyscyplina_Naukowa", on_delete=models.CASCADE
    )

    class Meta:
        unique_together = [("uczelnia", "dyscyplina_naukowa")]
        verbose_name = "Dyscyplina nieraportowana 2022-2025"
        verbose_name_plural = "Dyscypliny nieraportowane 2022-2025"
