# -*- encoding: utf-8 -*-

from django.db import models
from lxml.etree import Element, SubElement

from bpp.models.abstract import ModelZAdnotacjami, ModelZNazwa


class Konferencja(ModelZNazwa, ModelZAdnotacjami):
    nazwa = models.TextField(
        max_length=512,
        db_index=True)

    skrocona_nazwa = models.CharField(
        "Skrócona nazwa",
        max_length=250,
        null=True,
        blank=True,
        db_index=True
    )

    rozpoczecie = models.DateField(
        "Rozpoczęcie",
        null=True,
        blank=True
    )

    zakonczenie = models.DateField(
        "Zakończenie",
        null=True,
        blank=True
    )

    miasto = models.CharField(
        "Miasto",
        max_length=100,
        null=True,
        blank=True
    )

    panstwo = models.CharField(
        "Państwo",
        max_length=100,
        null=True,
        blank=True
    )

    baza_scopus = models.BooleanField(
        "Indeksowana w SCOPUS?",
        default=False
    )

    baza_wos = models.BooleanField(
        "Indeksowana w WOS?",
        default=False
    )

    baza_inna = models.CharField(
        "Indeksowana w...",
        max_length=200,
        help_text="Wpisz listę innych baz czasopism i abstraktów, w których indeksowana "
                  "była ta konferencja. Rozdziel średnikiem.",
        blank=True,
        null=True,
    )

    class Meta:
        unique_together = ('nazwa', 'rozpoczecie')
        ordering = ('-rozpoczecie', 'nazwa')
        verbose_name = 'konferencja'
        verbose_name_plural = 'konferencje'

    def __str__(self):
        ret = self.nazwa
        if self.baza_scopus:
            ret += " [Scopus]"
        if self.baza_wos:
            ret += " [WoS]"
        if self.baza_inna:
            ret += f" [{ self.baza_inna }]"
        return ret

    def eksport_pbn_serializuj(self, tagname='conference'):
        element = Element(tagname)

        name = SubElement(element, "name")
        name.text = self.nazwa

        if self.skrocona_nazwa:
            short_name = SubElement(element, "short-name")
            short_name.text = self.skrocona_nazwa

        if self.rozpoczecie:
            start_date = SubElement(element, "start-date")
            start_date.text = str(self.rozpoczecie)

        if self.zakonczenie:
            end_date = SubElement(element, "end-date")
            end_date.text = str(self.zakonczenie)

        if self.miasto:
            miasto = SubElement(element, "location")
            miasto.text = self.miasto

        if self.panstwo:
            panstwo = SubElement(element, "country")
            panstwo.text = self.panstwo

        if self.baza_wos:
            bw = SubElement(element, "web-of-science-indexed")
            bw.text = "true"

        if self.baza_scopus:
            bs = SubElement(element, "scopus-indexed")
            bs.text = "true"

        if self.baza_inna:
            bi = SubElement(element, "other-indexes")
            bi.text = self.baza_inna

        return element
