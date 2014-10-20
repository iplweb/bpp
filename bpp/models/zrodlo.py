# -*- encoding: utf-8 -*-

"""
Źródła.
"""
from autoslug import AutoSlugField

from django.db import models
from bpp.util import FulltextSearchMixin
from djorm_pgfulltext.fields import VectorField
from djorm_pgfulltext.models import SearchManager

from bpp.fields import YearField

from bpp.models.abstract import ModelZNazwa, ModelZAdnotacjami, ModelZISSN, \
    ModelPunktowanyBaza

from bpp.jezyk_polski import czasownik_byc


class Rodzaj_Zrodla(ModelZNazwa):
    class Meta:
        verbose_name = 'rodzaj źródła'
        verbose_name_plural = 'rodzaje źródeł'
        app_label = 'bpp'


class Zasieg_Zrodla(ModelZNazwa):
    class Meta:
        verbose_name = 'zasięg źródła'
        verbose_name_plural = 'zasięg źródeł'
        app_label = 'bpp'


class Redakcja_Zrodla(models.Model):
    """Informacja o tym, że ktoś jest redaktorem danego źródła - w latach,
    od - do."""
    zrodlo = models.ForeignKey('bpp.Zrodlo')
    od_roku = YearField()
    do_roku = YearField(null=True, blank=True)
    redaktor = models.ForeignKey('bpp.Autor')

    class Meta:
        app_label = 'bpp'
        verbose_name = 'redaktor źródła'
        verbose_name_plural = 'redaktorzy źródła'

    def __unicode__(self):
        buf = u"Redaktorem od %s " % self.od_roku

        if self.do_roku is not None:
            key = 'czas_przeszly'
            buf += 'do %s ' % self.do_roku
        else:
            key = 'czas_terazniejszy'

        if self.redaktor.plec is not None:
            skrot = self.redaktor.plec.skrot
        else:
            skrot = 'default'
        buf += czasownik_byc.get(key).get(
            skrot, czasownik_byc.get(key)['default'])

        buf += " " + unicode(self.redaktor)
        return buf

# TODO: sprawdzanie dla redakcja_zrodla, czy rok od jest > niz rok do <

class Punktacja_Zrodla(ModelPunktowanyBaza, models.Model):
    """Informacja o punktacji danego źródła w danym roku"""
    zrodlo = models.ForeignKey('Zrodlo')
    rok = YearField()

    def __unicode__(self):
        return u"Punktacja źródła za rok %s" % self.rok

    class Meta:
        verbose_name = 'punktacja źródła'
        verbose_name_plural = 'punktacja źródła'
        ordering = ['zrodlo__nazwa', 'rok']
        unique_together = [('zrodlo', 'rok')]
        app_label = 'bpp'


class ZrodloManager(FulltextSearchMixin, models.Manager):
    pass


class Zrodlo(ModelZAdnotacjami, ModelZISSN):
    rodzaj = models.ForeignKey(Rodzaj_Zrodla)
    nazwa = models.CharField(max_length=1024, db_index=True)
    skrot = models.CharField("Skrót", max_length=512, db_index=True)

    nazwa_alternatywna = models.CharField(
        max_length=1024, db_index=True, blank=True, null=True)
    skrot_nazwy_alternatywnej = models.CharField(
        max_length=512, blank=True, null=True, db_index=True)

    zasieg = models.ForeignKey(
        Zasieg_Zrodla, null=True, blank=True, default=None)

    www = models.URLField("WWW", max_length=1024, blank=True, null=True)

    poprzednia_nazwa = models.CharField(
        "Poprzedni tytuł", max_length=1024, db_index=True, blank=True,
        null=True)

    search = VectorField()

    objects = ZrodloManager()

    slug = AutoSlugField(
        populate_from='nazwa',
        unique=True)

    def __unicode__(self):
        ret = u"%s" % self.nazwa

        if self.nazwa_alternatywna:
            ret += u" (%s)" % self.nazwa_alternatywna

        if self.poprzednia_nazwa:
            ret += u" (d. %s)" % (self.poprzednia_nazwa)

        return ret

    class Meta:
        verbose_name = 'źródło'
        verbose_name_plural = 'źródła'
        ordering = ['nazwa']
        app_label = 'bpp'

    def prace_w_latach(self):
        from bpp.models import Wydawnictwo_Ciagle

        return Wydawnictwo_Ciagle.objects.filter(
            zrodlo=self).values_list(
            'rok', flat=True).distinct().order_by('rok')
