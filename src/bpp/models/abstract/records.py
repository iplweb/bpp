"""
Modele bazowe dla rekordów BPP.
"""

from django.db import models

from bpp.models.util import ModelZOpisemBibliograficznym

from .identifiers import ModelZPBN_ID
from .search import ModelPrzeszukiwalny, ModelZLegacyData


class RekordBPPBaza(
    ModelZPBN_ID, ModelZOpisemBibliograficznym, ModelPrzeszukiwalny, ModelZLegacyData
):
    """Klasa bazowa wszystkich rekordów (patenty, prace doktorskie,
    habilitacyjne, wydawnictwa zwarte i ciągłe)"""

    class Meta:
        abstract = True


class Wydawnictwo_Baza(RekordBPPBaza):
    """Klasa bazowa wydawnictw (prace doktorskie, habilitacyjne, wydawnictwa
    ciągłe, zwarte -- bez patentów)."""

    class Meta:
        abstract = True

    def __str__(self):
        return self.tytul_oryginalny


class ModelWybitny(models.Model):
    praca_wybitna = models.BooleanField(default=False)
    uzasadnienie_wybitnosci = models.TextField(
        "Uzasadnienie wybitności", default="", blank=True
    )

    class Meta:
        abstract = True
