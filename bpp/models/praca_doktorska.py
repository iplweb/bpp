# -*- encoding: utf-8 -*-

from django.db import models
from djorm_pgfulltext.models import SearchManager
from bpp.models import Autor, ModelPunktowany, Jednostka
from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte_Baza

class Praca_Doktorska_Baza(Wydawnictwo_Zwarte_Baza):

    autor = models.ForeignKey(Autor)
    jednostka = models.ForeignKey(Jednostka)

    objects = SearchManager(
        fields=['tytul_oryginalny', 'tytul'],
        config='bpp_nazwy_wlasne')

    class Meta:
        abstract = True


class Praca_Doktorska(Praca_Doktorska_Baza):

    objects = SearchManager(
        fields=['tytul_oryginalny', 'tytul'],
        config='bpp_nazwy_wlasne')

    class Meta:
        verbose_name = 'praca doktorska'
        verbose_name_plural = 'prace doktorskie'
        app_label = 'bpp'


