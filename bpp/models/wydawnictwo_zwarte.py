# -*- encoding: utf-8 -*-

from django.db import models
from djorm_pgfulltext.models import SearchManager

from bpp.models import dodaj_autora
from bpp.models.abstract import \
    BazaModeluOdpowiedzialnosciAutorow, DwaTytuly, ModelZRokiem, \
    ModelZWWW, ModelAfiliowanyRecenzowany, ModelPunktowany, ModelTypowany, \
    ModelZeSzczegolami, ModelZInformacjaZ, ModelZeStatusem, ModelZISBN, ModelZAdnotacjami, ModelZCharakterem, Wydawnictwo_Baza
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
        ordering = ('kolejnosc', )
        unique_together = \
            [('rekord', 'autor', 'typ_odpowiedzialnosci'),
             ('rekord', 'kolejnosc')]


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
                        Wydawnictwo_Zwarte_Baza, ModelZCharakterem):
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


