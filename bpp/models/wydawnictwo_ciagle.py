# -*- encoding: utf-8 -*-

from django.db import models
from djorm_pgfulltext.models import SearchManager
from secure_input.utils import safe_html

from bpp.models.abstract import BazaModeluOdpowiedzialnosciAutorow, DwaTytuly, ModelZRokiem, \
    ModelZWWW, ModelAfiliowanyRecenzowany, ModelPunktowany, ModelTypowany, \
    ModelZeSzczegolami, ModelZInformacjaZ, ModelZeStatusem, ModelZISSN, \
    ModelZAdnotacjami, ModelZCharakterem, Wydawnictwo_Baza
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
             ('rekord', 'kolejnosc')]



class Wydawnictwo_Ciagle(ZapobiegajNiewlasciwymCharakterom,
                         Wydawnictwo_Baza, DwaTytuly, ModelZRokiem,
                         ModelZeStatusem,
                         ModelZWWW, ModelAfiliowanyRecenzowany,
                         ModelPunktowany, ModelTypowany, ModelZeSzczegolami,
                         ModelZISSN, ModelZInformacjaZ, ModelZAdnotacjami,
                         ModelZCharakterem):
    """Wydawnictwo ciągłe, czyli artykuły z czasopism, komentarze, listy
    do redakcji, publikacje w suplemencie, etc. """

    autorzy = models.ManyToManyField('Autor', through=Wydawnictwo_Ciagle_Autor)

    zrodlo = models.ForeignKey('Zrodlo', null=True, verbose_name="Źródło")

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


