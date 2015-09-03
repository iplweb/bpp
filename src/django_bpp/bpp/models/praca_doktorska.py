# -*- encoding: utf-8 -*-

from django.db import models
from djorm_pgfulltext.models import SearchManager

from bpp.models import Autor, Jednostka
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte_Baza


class Praca_Doktorska_Baza(Wydawnictwo_Zwarte_Baza):

    autor = models.ForeignKey(Autor, unique=True)
    jednostka = models.ForeignKey(Jednostka)

    objects = SearchManager(
        fields=['tytul_oryginalny', 'tytul'],
        config='bpp_nazwy_wlasne')

    class Meta:
        abstract = True


class Praca_Doktorska(Praca_Doktorska_Baza):

    promotor = models.ForeignKey(Autor, related_name="promotor_doktoratu", blank=True, null=True)

    objects = SearchManager(
        fields=['tytul_oryginalny', 'tytul'],
        config='bpp_nazwy_wlasne')

    class Meta:
        verbose_name = 'praca doktorska'
        verbose_name_plural = 'prace doktorskie'
        app_label = 'bpp'


