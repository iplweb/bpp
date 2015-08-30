# -*- encoding: utf-8 -*-

from django.db import models
from django.utils.functional import cached_property
from djorm_pgfulltext.models import SearchManager
from lxml.etree import Element, SubElement

from bpp.models import dodaj_autora
from bpp.models.abstract import \
    BazaModeluOdpowiedzialnosciAutorow, DwaTytuly, ModelZRokiem, \
    ModelZWWW, ModelAfiliowanyRecenzowany, ModelPunktowany, ModelTypowany, \
    ModelZeSzczegolami, ModelZInformacjaZ, ModelZeStatusem, ModelZISBN, ModelZAdnotacjami, ModelZCharakterem, \
    Wydawnictwo_Baza, \
    PBNSerializerHelperMixin
from bpp.models.autor import Autor
from bpp.models.util import ZapobiegajNiewlasciwymCharakterom


class Wydawnictwo_Zwarte_Autor(BazaModeluOdpowiedzialnosciAutorow):
    """Model zawierający informację o przywiązaniu autorów do wydawnictwa
    zwartego."""
    rekord = models.ForeignKey('Wydawnictwo_Zwarte')

    class Meta:
        verbose_name = 'powiązanie autora z wyd. zwartym'
        verbose_name_plural = 'powiązania autorów z wyd. zwartymi'
        app_label = 'bpp'
        ordering = ('kolejnosc',)
        unique_together = \
            [('rekord', 'autor', 'typ_odpowiedzialnosci'),
             # Tu musi być autor, inaczej admin nie pozwoli wyedytować
             ('rekord', 'autor', 'kolejnosc')]


class Wydawnictwo_Zwarte_Baza(
    Wydawnictwo_Baza, DwaTytuly, ModelZRokiem, ModelZeStatusem,
    ModelZWWW, ModelAfiliowanyRecenzowany,
    ModelPunktowany, ModelTypowany, ModelZeSzczegolami,
    ModelZInformacjaZ, ModelZISBN, ModelZAdnotacjami):
    """Baza dla klas Wydawnictwo_Zwarte oraz Praca_Doktorska_Lub_Habilitacyjna
    """

    miejsce_i_rok = models.CharField(
        max_length=256, blank=True, null=True, help_text="""Przykładowo:
        Warszawa 2012. Wpisz proszę najpierw miejsce potem rok; oddziel
        spacją.""")

    wydawnictwo = models.CharField(max_length=256, null=True, blank=True)

    redakcja = models.TextField(null=True, blank=True)

    class Meta:
        abstract = True

class Wydawnictwo_Zwarte(ZapobiegajNiewlasciwymCharakterom,
                         Wydawnictwo_Zwarte_Baza, ModelZCharakterem,
                         PBNSerializerHelperMixin):
    """Wydawnictwo zwarte, czyli: książki, broszury, skrypty, fragmenty,
    doniesienia zjazdowe."""

    objects = SearchManager(
        fields=['tytul_oryginalny', 'tytul'],
        config='bpp_nazwy_wlasne')

    autorzy = models.ManyToManyField(Autor, through=Wydawnictwo_Zwarte_Autor)

    liczba_znakow_wydawniczych = models.IntegerField(
        'Liczba znaków wydawniczych', blank=True, null=True)

    wydawnictwo_nadrzedne = models.ForeignKey(
        'self', blank=True, null=True, help_text="""Jeżeli dodajesz rozdział,
        tu wybierz pracę, w ramach której dany rozdział występuje.""")

    def dodaj_autora(self, autor, jednostka, zapisany_jako=None,
                     typ_odpowiedzialnosci_skrot='aut.', kolejnosc=None):
        return dodaj_autora(
            Wydawnictwo_Zwarte_Autor, self, autor, jednostka, zapisany_jako,
            typ_odpowiedzialnosci_skrot, kolejnosc)

    class Meta:
        verbose_name = 'wydawnictwo zwarte'
        verbose_name_plural = 'wydawnictwa zwarte'
        app_label = 'bpp'

    def guess_pbn_type(self):
        if self.charakter_formalny.charakter_pbn != None:
            return self.charakter_formalny.charakter_pbn.identyfikator

        tks = self.typ_kbn.skrot

        if self.is_chapter:
            return 'chapter-in-a-book'

        if tks == 'PNP':
            return 'popular-science-book'

        if tks == 'PO' or tks == 'PP':
            return 'scholarly-monograph'

    @cached_property
    def is_chapter(self):
        return self.charakter_formalny.skrot in ['ROZ', 'ROZS']

    def serializuj_dla_pbn(self, wydzial):
        toplevel = Element('book')
        if self.is_chapter:
            toplevel = Element('chapter')

        self.serializuj_typowe_elementy(toplevel, wydzial, Wydawnictwo_Zwarte_Autor)

        if not self.is_chapter and self.isbn:
            isbn = SubElement(toplevel, 'isbn')
            isbn.text = self.isbn.replace(".", "").strip()

        # if self.wydawnictwo_nadrzedne:
        #    series = SubElement(toplevel, 'series')
        #    series.text = self.wydawnictwo_nadrzedne.tytul_oryginalny

        #     <number-in-series>3</number-in-series>

        #     <edition>2</edition>
        #     <volume>15</volume>
        #     <pages>374</pages>

        if self.miejsce_i_rok:
            try:
                miejsce, rok = self.miejsce_i_rok.split(" ")
            except ValueError:
                miejsce = self.miejsce_i_rok

            # if miejsce:
            #     publication_place = SubElement(toplevel, 'publication-place')
            #     publication_place.text = miejsce

        #if self.wydawnictwo:
        #    publisher_name = SubElement(toplevel, 'publisher-name')
        #    publisher_name.text = self.wydawnictwo

        return toplevel