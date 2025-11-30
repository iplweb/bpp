"""
Modele abstrakcyjne związane z podstawowymi polami publikacji.
"""

from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import CASCADE, SET_NULL

from bpp.fields import YearField

from .utils import get_liczba_arkuszy_wydawniczych


class ModelZeZnakamiWydawniczymi(models.Model):
    liczba_znakow_wydawniczych = models.IntegerField(
        "Liczba znaków wydawniczych", blank=True, null=True, db_index=True
    )

    class Meta:
        abstract = True

    def ma_wymiar_wydawniczy(self):
        return self.liczba_znakow_wydawniczych is not None

    def wymiar_wydawniczy_w_arkuszach(self):
        return f"{get_liczba_arkuszy_wydawniczych(self.liczba_znakow_wydawniczych):.2f}"


class ModelRecenzowany(models.Model):
    """Model zawierający informacje o afiliowaniu/recenzowaniu pracy."""

    recenzowana = models.BooleanField(default=False, db_index=True)

    class Meta:
        abstract = True


class ModelTypowany(models.Model):
    """Model zawierający typ MNiSW/MEiN oraz język."""

    typ_kbn = models.ForeignKey("Typ_KBN", CASCADE, verbose_name="typ MNiSW/MEiN")
    jezyk = models.ForeignKey(
        "Jezyk", CASCADE, verbose_name="Język", limit_choices_to={"widoczny": True}
    )
    jezyk_alt = models.ForeignKey(
        "Jezyk",
        SET_NULL,
        verbose_name="Język alternatywny",
        null=True,
        blank=True,
        related_name="+",
    )

    jezyk_orig = models.ForeignKey(
        "Jezyk",
        SET_NULL,
        verbose_name="Język oryginalny",
        help_text="Dla tłumaczeń. Wartość eksportowana do PBN. ",
        related_name="+",
        null=True,
        blank=True,
    )

    class Meta:
        abstract = True


class ModelZRokiem(models.Model):
    """Model zawierający pole "Rok" """

    rok = YearField(
        help_text="""Rok uwzględniany przy wyszukiwaniu i raportach
        KBN/MNiSW)""",
        db_index=True,
        validators=[MinValueValidator(0)],
    )

    class Meta:
        abstract = True


class ModelZSeria_Wydawnicza(models.Model):
    seria_wydawnicza = models.ForeignKey(
        "bpp.Seria_Wydawnicza", CASCADE, blank=True, null=True
    )

    numer_w_serii = models.CharField(max_length=512, blank=True, default="")

    class Meta:
        abstract = True


class ModelZKonferencja(models.Model):
    konferencja = models.ForeignKey("bpp.Konferencja", CASCADE, blank=True, null=True)

    class Meta:
        abstract = True
