# -*- encoding: utf-8 -*-

"""
Źródła.
"""
from autoslug import AutoSlugField

from django.db import models
from django.db.models import CASCADE, CASCADE, SET_NULL
from django.urls.base import reverse
from lxml.etree import Element, SubElement
from bpp.models.system import Jezyk
from bpp.util import FulltextSearchMixin
from django.contrib.postgres.search import SearchVectorField as VectorField
from bpp.fields import YearField, DOIField

from bpp.models.abstract import (
    ModelZNazwa,
    ModelZAdnotacjami,
    ModelZISSN,
    ModelPunktowanyBaza,
)

from bpp.jezyk_polski import czasownik_byc


class Rodzaj_Zrodla(ModelZNazwa):
    class Meta:
        verbose_name = "rodzaj źródła"
        verbose_name_plural = "rodzaje źródeł"
        app_label = "bpp"


class Zasieg_Zrodla(ModelZNazwa):
    class Meta:
        verbose_name = "zasięg źródła"
        verbose_name_plural = "zasięg źródeł"
        app_label = "bpp"


class Redakcja_Zrodla(models.Model):
    """Informacja o tym, że ktoś jest redaktorem danego źródła - w latach,
    od - do."""

    zrodlo = models.ForeignKey("bpp.Zrodlo", CASCADE)
    od_roku = YearField()
    do_roku = YearField(null=True, blank=True)
    redaktor = models.ForeignKey("bpp.Autor", CASCADE)

    class Meta:
        app_label = "bpp"
        verbose_name = "redaktor źródła"
        verbose_name_plural = "redaktorzy źródła"

    def __str__(self):
        buf = "Redaktorem od %s " % self.od_roku

        if self.do_roku is not None:
            key = "czas_przeszly"
            buf += "do %s " % self.do_roku
        else:
            key = "czas_terazniejszy"

        if self.redaktor.plec is not None:
            skrot = self.redaktor.plec.skrot
        else:
            skrot = "default"
        buf += czasownik_byc.get(key).get(skrot, czasownik_byc.get(key)["default"])

        buf += " " + str(self.redaktor)
        return buf


# TODO: sprawdzanie dla redakcja_zrodla, czy rok od jest > niz rok do <
class Punktacja_Zrodla(ModelPunktowanyBaza, models.Model):
    """Informacja o punktacji danego źródła w danym roku"""

    zrodlo = models.ForeignKey("Zrodlo", CASCADE)
    rok = YearField()

    def __str__(self):
        return "Punktacja źródła za rok %s" % self.rok

    class Meta:
        verbose_name = "punktacja źródła"
        verbose_name_plural = "punktacja źródła"
        ordering = ["zrodlo__nazwa", "rok"]
        unique_together = [("zrodlo", "rok")]
        app_label = "bpp"


class ZrodloManager(FulltextSearchMixin, models.Manager):
    pass


class Zrodlo(ModelZAdnotacjami, ModelZISSN):
    nazwa = models.CharField(max_length=1024, db_index=True)
    skrot = models.CharField("Skrót", max_length=512, db_index=True)

    rodzaj = models.ForeignKey(Rodzaj_Zrodla, CASCADE)

    nazwa_alternatywna = models.CharField(
        max_length=1024, db_index=True, blank=True, null=True
    )
    skrot_nazwy_alternatywnej = models.CharField(
        max_length=512, blank=True, null=True, db_index=True
    )

    zasieg = models.ForeignKey(
        Zasieg_Zrodla, SET_NULL, null=True, blank=True, default=None
    )

    www = models.URLField("WWW", max_length=1024, blank=True, null=True, db_index=True)

    doi = DOIField("DOI", blank=True, null=True, db_index=True)

    poprzednia_nazwa = models.CharField(
        "Poprzedni tytuł", max_length=1024, db_index=True, blank=True, null=True
    )

    openaccess_tryb_dostepu = models.CharField(
        verbose_name="OpenAccess: tryb dostępu",
        max_length=50,
        db_index=True,
        blank=True,
        choices=[("FULL", "pełny"), ("PARTIAL", "częściowy")],
    )

    openaccess_licencja = models.ForeignKey(
        "Licencja_OpenAccess",
        CASCADE,
        verbose_name="OpenAccess: licencja",
        blank=True,
        null=True,
    )

    jezyk = models.ForeignKey(Jezyk, CASCADE, null=True, blank=True)
    wydawca = models.CharField(max_length=250, blank=True)

    search = VectorField()

    objects = ZrodloManager()

    slug = AutoSlugField(populate_from="nazwa", unique=True)

    def get_absolute_url(self):
        return reverse("bpp:browse_zrodlo", args=(self.slug,))

    def __str__(self):
        ret = "%s" % self.nazwa

        # if self.nazwa_alternatywna:
        #     ret += " (%s)" % self.nazwa_alternatywna
        #
        if self.poprzednia_nazwa:
            ret += " (d. %s)" % (self.poprzednia_nazwa)

        return ret

    class Meta:
        verbose_name = "źródło"
        verbose_name_plural = "źródła"
        ordering = ["nazwa"]
        app_label = "bpp"

    def prace_w_latach(self):
        from bpp.models import Wydawnictwo_Ciagle

        return (
            Wydawnictwo_Ciagle.objects.filter(zrodlo=self)
            .values_list("rok", flat=True)
            .distinct()
            .order_by("rok")
        )

    def eksport_pbn_serializuj(self):
        journal = Element("journal")

        title_kw = {}
        if self.jezyk != None:
            title_kw["lang"] = self.jezyk.get_skrot_dla_pbn()

        title = SubElement(journal, "title", **title_kw)
        title.text = self.nazwa

        if self.issn:
            issn = SubElement(journal, "issn")
            issn.text = self.issn

        if self.e_issn:
            eissn = SubElement(journal, "eissn")
            eissn.text = self.e_issn

        if self.doi:
            doi = SubElement(journal, "doi")
            doi.text = self.doi

        if self.www:
            website = SubElement(journal, "website", href=self.www)

        system_identifier = SubElement(journal, "system-identifier")
        system_identifier.text = str(self.pk)

        if self.wydawca:
            publisher_name = SubElement(journal, "publisher-name")
            publisher_name.text = self.wydawca

        return journal
