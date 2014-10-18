# -*- encoding: utf-8 -*-

"""
Małe klasy pomocnicze dla całego systemu
"""

from django.db import models
from bpp.models.abstract import ModelZNazwa, NazwaISkrot, ModelPunktowany


class Charakter_Formalny(NazwaISkrot):
    """Bazowa klasa dla charakterów formalnych. """

    publikacja = models.BooleanField(help_text="""Jest charakterem dla publikacji""", default=False)
    streszczenie = models.BooleanField(help_text="""Jest charakterem dla streszczeń""", default=False)

    class Meta:
        ordering = ['nazwa']
        app_label = 'bpp'
        verbose_name = "charakter formalny"
        verbose_name_plural = 'charaktery formalne'


class Status_Korekty(ModelZNazwa):
    class Meta:
        verbose_name = 'status korekty'
        verbose_name_plural = 'statusy korekty'
        app_label = 'bpp'


class Zrodlo_Informacji(ModelZNazwa):
    class Meta:
        verbose_name = 'źródło informacji o bibliografii'
        verbose_name_plural = 'źródła informacji o bibliografii'
        app_label = 'bpp'


class Typ_Odpowiedzialnosci(NazwaISkrot):
    class Meta:
        verbose_name = 'typ odpowiedzialności autora'
        verbose_name_plural = 'typy odpowiedzialności autorów'
        ordering = ['nazwa']
        app_label = 'bpp'

    def __unicode__(self):
        return self.nazwa

class Jezyk(NazwaISkrot):

    class Meta:
        verbose_name = 'język'
        verbose_name_plural = 'języki'
        ordering = ['nazwa']
        app_label = 'bpp'


class Typ_KBN(NazwaISkrot):
    class Meta:
        verbose_name = 'typ KBN'
        verbose_name_plural = 'typy KBN'
        ordering = ['nazwa']
        app_label = 'bpp'

