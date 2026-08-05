"""
Modele bazowe dla rekordów BPP.
"""

from django.contrib.contenttypes.fields import GenericRelation
from django.db import models

from bpp.models.util import ModelZOpisemBibliograficznym

from .identifiers import ModelZPBN_ID
from .search import ModelPrzeszukiwalny, ModelZLegacyData


class RekordBPPBaza(
    ModelZPBN_ID, ModelZOpisemBibliograficznym, ModelPrzeszukiwalny, ModelZLegacyData
):
    """Klasa bazowa wszystkich rekordów (patenty, prace doktorskie,
    habilitacyjne, wydawnictwa zwarte i ciągłe)"""

    # ``Grant_Rekordu`` wiąże rekord z numerem grantu przez
    # ``GenericForeignKey``. Bez odwrotnej ``GenericRelation`` nie da się
    # tego prefetchować od strony rekordu, a eksport CERIF osadza w każdej
    # publikacji projekt grantu (``Publication/OriginatesFrom``) — bez
    # prefetcha byłoby to kilka zapytań NA REKORD przy pełnym harveście.
    #
    # ``GenericRelation`` nie tworzy kolumny ani indeksu, więc nie wymaga
    # migracji. Zmienia natomiast kaskadę kasowania: usunięcie rekordu
    # usuwa teraz jego wiersze ``Grant_Rekordu`` zamiast zostawiać je
    # jako sieroty wskazujące na nieistniejący ``object_id``.
    granty_rekordu = GenericRelation("bpp.Grant_Rekordu")

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
