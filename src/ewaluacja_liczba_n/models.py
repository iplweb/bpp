from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator
from django.db import models

from bpp.fields import YearField
from bpp.models.autor import Autor
from bpp.models.dyscyplina_naukowa import Dyscyplina_Naukowa
from bpp.models.uczelnia import Uczelnia

from .fields import LiczbaNField


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

    def __str__(self):
        return f"{self.dyscyplina_naukowa.nazwa} -> {self.liczba_n}"


class IloscUdzialowDlaAutoraBase(models.Model):
    """Abstract base model for author share calculations"""

    autor = models.ForeignKey(Autor, on_delete=models.CASCADE)
    dyscyplina_naukowa = models.ForeignKey(Dyscyplina_Naukowa, on_delete=models.CASCADE)
    ilosc_udzialow = LiczbaNField()
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


class IloscUdzialowDlaAutoraZaRok(IloscUdzialowDlaAutoraBase):
    """Shares for an author in a specific year"""

    rok = YearField()
    autor_dyscyplina = models.ForeignKey(
        "bpp.Autor_Dyscyplina",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        help_text="Link do oryginalnego rekordu Autor_Dyscyplina za dany rok",
    )

    # Override ilosc_udzialow to add validator for yearly limit
    ilosc_udzialow = LiczbaNField(validators=[MaxValueValidator(4)])

    class Meta:
        verbose_name = "Ilość udziałów dla autora za rok"
        verbose_name_plural = "Ilości udziałów dla autorów za rok"
        unique_together = [
            ("autor", "dyscyplina_naukowa", "rok"),
        ]


class IloscUdzialowDlaAutoraZaCalosc(IloscUdzialowDlaAutoraBase):
    """Total shares for an author across the entire evaluation period"""

    rodzaj_autora = models.ForeignKey(
        "ewaluacja_common.Rodzaj_Autora",
        on_delete=models.CASCADE,
        verbose_name="Rodzaj autora",
        null=True,
        blank=True,
    )

    komentarz = models.TextField(
        blank=True,
        default="",
        help_text="Dodatkowe informacje o wyliczeniach",
    )

    # Override ilosc_udzialow to add validator for total period limit (4 years * 4 = 16)
    ilosc_udzialow = LiczbaNField(validators=[MaxValueValidator(16)])

    class Meta:
        verbose_name = "Ilość udziałów dla autora za cały okres"
        verbose_name_plural = "Ilości udziałów dla autorów za cały okres"
        unique_together = [
            ("autor", "dyscyplina_naukowa", "rodzaj_autora"),
        ]


class DyscyplinaNieRaportowana(models.Model):
    uczelnia = models.ForeignKey("bpp.Uczelnia", on_delete=models.CASCADE)
    dyscyplina_naukowa = models.ForeignKey(
        "bpp.Dyscyplina_Naukowa", on_delete=models.CASCADE
    )
    liczba_n = LiczbaNField(
        default=0, help_text="Liczba N dla dyscypliny (poniżej progu raportowania)"
    )

    class Meta:
        unique_together = [("uczelnia", "dyscyplina_naukowa")]
        verbose_name = "Dyscyplina nieraportowana 2022-2025"
        verbose_name_plural = "Dyscypliny nieraportowane 2022-2025"
