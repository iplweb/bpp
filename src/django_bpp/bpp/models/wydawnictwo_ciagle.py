# -*- encoding: utf-8 -*-

from django.db import models
from djorm_pgfulltext.models import SearchManager
from lxml.etree import SubElement, Element
from secure_input.utils import safe_html

from bpp.models.abstract import BazaModeluOdpowiedzialnosciAutorow, DwaTytuly, ModelZRokiem, \
    ModelZWWW, ModelAfiliowanyRecenzowany, ModelPunktowany, ModelTypowany, \
    ModelZeSzczegolami, ModelZInformacjaZ, ModelZeStatusem, ModelZISSN, \
    ModelZAdnotacjami, ModelZCharakterem, Wydawnictwo_Baza, PBNSerializerHelperMixin
from bpp.models.util import dodaj_autora, ZapobiegajNiewlasciwymCharakterom


class Wydawnictwo_Ciagle_Autor(BazaModeluOdpowiedzialnosciAutorow):
    """Powiązanie autora do wydawnictwa ciągłego."""
    rekord = models.ForeignKey('Wydawnictwo_Ciagle')

    class Meta:
        verbose_name = 'powiązanie autora z wyd. ciągłym'
        verbose_name_plural = 'powiązania autorów z wyd. ciągłymi'
        app_label = 'bpp'
        ordering = ('kolejnosc', )
        unique_together = \
            [('rekord', 'autor', 'typ_odpowiedzialnosci'),
              # Tu musi być autor, inaczej admin nie pozwoli wyedytować
             ('rekord', 'autor', 'kolejnosc')]


TYP_KBN_MAP = {
    'PO': 'original-article',
    'PW': 'original-article',
    'PP': 'review-article',
    'PNP': 'popular-science-article',
    '000': 'others-citable'
}

class Wydawnictwo_Ciagle(ZapobiegajNiewlasciwymCharakterom,
                         Wydawnictwo_Baza, DwaTytuly, ModelZRokiem,
                         ModelZeStatusem,
                         ModelZWWW, ModelAfiliowanyRecenzowany,
                         ModelPunktowany, ModelTypowany, ModelZeSzczegolami,
                         ModelZISSN, ModelZInformacjaZ, ModelZAdnotacjami,
                         ModelZCharakterem, PBNSerializerHelperMixin):
    """Wydawnictwo ciągłe, czyli artykuły z czasopism, komentarze, listy
    do redakcji, publikacje w suplemencie, etc. """

    autorzy = models.ManyToManyField('Autor', through=Wydawnictwo_Ciagle_Autor)

    zrodlo = models.ForeignKey('Zrodlo', null=True, verbose_name="Źródło", on_delete=models.SET_NULL)

    # To pole nie służy w bazie danych do niczego - jedyne co, to w adminie
    # w wygodny sposób chcemy wyświetlić przycisk 'uzupelnij punktacje', jak
    # się okazuje, przy używaniu standardowych procedur w Django jest to
    # z tego co na dziś dzień umiem, mocno utrudnione.
    uzupelnij_punktacje = models.BooleanField(default=False)

    objects = SearchManager(
        fields=['tytul_oryginalny', 'tytul'],
        config='bpp_nazwy_wlasne')

    def dodaj_autora(self, autor, jednostka, zapisany_jako=None,
              typ_odpowiedzialnosci_skrot='aut.', kolejnosc=None):
        return dodaj_autora(
            Wydawnictwo_Ciagle_Autor, self, autor, jednostka, zapisany_jako,
            typ_odpowiedzialnosci_skrot, kolejnosc)
    
    def clean(self):
        self.tytul_oryginalny = safe_html(self.tytul_oryginalny)
        self.tytul = safe_html(self.tytul)

    class Meta:
        verbose_name = "wydawnictwo ciągłe"
        verbose_name_plural = "wydawnictwa ciągłe"
        app_label = 'bpp'

    def guess_pbn_type(self):
        if self.charakter_formalny.charakter_pbn != None:
            return self.charakter_formalny.charakter_pbn.identyfikator

        tks = self.typ_kbn.skrot
        if TYP_KBN_MAP.get(tks):
            return TYP_KBN_MAP.get(tks)

    def serializuj_dla_pbn(self, wydzial):
        article = Element('article')
        self.serializuj_typowe_elementy(article, wydzial, Wydawnictwo_Ciagle_Autor)

        self.serializuj_is(article)

        if self.zrodlo is not None:
            article.append(self.zrodlo.serializuj_dla_pbn())

        if self.informacje.find("nr") >= 0:
            issue = SubElement(article, "issue")
            issue.text = self.informacje.split("nr")[1].strip().split(" ")[0]

        if self.informacje.find("vol.") >= 0:
            volume = SubElement(article, 'volume')
            volume.text = self.informacje.split("vol.")[1].strip().split(" ")[0]

        self.serializuj_strony(article)

        return article