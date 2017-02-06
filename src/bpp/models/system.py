# -*- encoding: utf-8 -*-

"""
Małe klasy pomocnicze dla całego systemu
"""

from django.db import models

from bpp.models.abstract import ModelZNazwa, NazwaISkrot

NAZWY_PRIMO = [
    u"",
    u"Artykuł",
    u"Książka",
    u"Zasób tekstowy",
    u"Rozprawa naukowa",
    u"Recenzja",
    u"Artykuł prasowy",
    u"Rozdział",
    u"Czasopismo",
    u"Dane badawcze",
    u"Materiał konferencyjny",
    u"Obraz",
    u"Baza",
    u"Zestaw danych statystycznych",
    u"Multimedia",
    u"Inny"
]

NAZWY_PRIMO = zip(NAZWY_PRIMO, NAZWY_PRIMO)

RODZAJE_DOKUMENTOW_PBN = [("article", "Artykuł"),
                          ("book", "Książka"),
                          ("chapter", "Rozdział")]


class Charakter_PBN(models.Model):
    wlasciwy_dla = models.CharField(max_length=20,
                                    choices=RODZAJE_DOKUMENTOW_PBN)
    identyfikator = models.CharField(max_length=100)
    opis = models.CharField(max_length=500)
    help_text = models.TextField(blank=True)

    class Meta:
        ordering = ['identyfikator']
        verbose_name = 'Charakter PBN'
        verbose_name_plural = 'Charaktery PBN'

    def __unicode__(self):
        return self.opis


class Charakter_Formalny(NazwaISkrot):
    """Bazowa klasa dla charakterów formalnych. """

    publikacja = models.BooleanField(help_text="""Jest charakterem dla publikacji""", default=False)
    streszczenie = models.BooleanField(help_text="""Jest charakterem dla streszczeń""", default=False)

    nazwa_w_primo = models.CharField("Nazwa w Primo", max_length=100, help_text="""
    Nazwa charakteru formalnego w wyszukiwarce Primo, eksponowana przez OAI-PMH. W przypadku,
    gdy to pole jest puste, prace o danym charakterze formalnym nie będą udostępniane przez
    protokół OAI-PMH.
    """, blank=True, default="", choices=NAZWY_PRIMO, db_index=True)

    charakter_pbn = models.ForeignKey(Charakter_PBN,
                                      verbose_name="Charakter PBN",
                                      blank=True, null=True, default=None,
                                      help_text="""Wartość wybrana w tym polu zostanie użyta jako zawartość tagu <is>
                                      w plikach eksportu do PBN""")

    artykul_pbn = models.BooleanField(verbose_name="Artykuł w PBN", help_text="""Wydawnictwa ciągłe posiadające
     ten charakter formalny zostaną włączone do eksportu PBN jako artykuły""", default=False)
    ksiazka_pbn = models.BooleanField(verbose_name="Książka w PBN", help_text="""Wydawnictwa zwarte posiadające ten
    charakter formalny zostaną włączone do eksportu PBN jako ksiażki""", default=False)
    rozdzial_pbn = models.BooleanField(verbose_name="Rozdział w PBN", help_text="""Wydawnictwa zwarte posiadające ten
    charakter formalny zostaną włączone do eksportu PBN jako rozdziały""", default=False)

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
        verbose_name = u'źródło informacji o bibliografii'
        verbose_name_plural = u'źródła informacji o bibliografii'
        app_label = 'bpp'


class Typ_Odpowiedzialnosci(NazwaISkrot):
    class Meta:
        verbose_name = u'typ odpowiedzialności autora'
        verbose_name_plural = u'typy odpowiedzialności autorów'
        ordering = ['nazwa']
        app_label = 'bpp'

    def __unicode__(self):
        return self.nazwa


class Jezyk(NazwaISkrot):
    skrot_dla_pbn = models.CharField(max_length=10, verbose_name="Skrót dla PBN", help_text="""
    Skrót nazwy języka używany w plikach eksportu do PBN.""", blank=True)

    class Meta:
        verbose_name = u'język'
        verbose_name_plural = u'języki'
        ordering = ['nazwa']
        app_label = 'bpp'

    def get_skrot_dla_pbn(self):
        if self.skrot_dla_pbn:
            return self.skrot_dla_pbn

        return self.skrot


class Typ_KBN(NazwaISkrot):
    artykul_pbn = models.BooleanField("Artykuł w PBN", help_text="""Wydawnictwa ciągłe posiadające
    ten typ KBN zostaną włączone do eksportu PBN jako artykuły""", default=False)

    class Meta:
        verbose_name = 'typ KBN'
        verbose_name_plural = 'typy KBN'
        ordering = ['nazwa']
        app_label = 'bpp'
