# -*- encoding: utf-8 -*-
from django.db import models
from django.utils import six

from bpp.models import BazaModeluOdpowiedzialnosciAutorow, Autor, \
    ModelZRokiem, ModelZeStatusem, ModelZWWW, ModelRecenzowany, \
    ModelZInformacjaZ, ModelZAdnotacjami, ModelZeSzczegolami, ModelPunktowany, \
    Charakter_Formalny, Jezyk
from bpp.models.abstract import RekordBPPBaza, ModelZAbsolutnymUrl
from bpp.models.util import dodaj_autora


class Patent_Autor(BazaModeluOdpowiedzialnosciAutorow):
    """Powiązanie autora do patentu."""
    rekord = models.ForeignKey('Patent', related_name="autorzy_set")

    class Meta:
        verbose_name = 'powiązanie autora z patentem'
        verbose_name_plural = 'powiązania autorów z patentami'
        app_label = 'bpp'
        ordering = ('kolejnosc',)
        unique_together = \
            [('rekord', 'autor', 'typ_odpowiedzialnosci'),
             # Tu musi być autor, inaczej admin nie pozwoli wyedytować
             ('rekord', 'autor', 'kolejnosc')]


@six.python_2_unicode_compatible
class Patent(RekordBPPBaza,
             ModelZRokiem,
             ModelZeStatusem,
             ModelZWWW,
             ModelRecenzowany,
             ModelPunktowany,
             ModelZeSzczegolami,
             ModelZInformacjaZ,
             ModelZAdnotacjami,
             ModelZAbsolutnymUrl):
    tytul_oryginalny = models.TextField("Tytuł oryginalny", db_index=True)

    data_zgloszenia = models.DateField(
        "Data zgłoszenia", null=True, blank=True)

    numer_zgloszenia = models.CharField(
        "Numer zgłoszenia", max_length=255, null=True, blank=True)

    data_decyzji = models.DateField(
        null=True, blank=True
    )

    numer_prawa_wylacznego = models.CharField(
        "Numer prawa wyłącznego", max_length=255, null=True, blank=True
    )

    rodzaj_prawa = models.ForeignKey(
        "bpp.Rodzaj_Prawa_Patentowego",
        null=True, blank=True
    )

    wdrozenie = models.NullBooleanField(
        "Wdrożenie",
    )

    wydzial = models.ForeignKey(
        "bpp.Wydzial",
        null=True,
        blank=True,
        on_delete=models.SET_NULL)

    autorzy = models.ManyToManyField(Autor, through=Patent_Autor)

    def dodaj_autora(self, autor, jednostka, zapisany_jako=None,
                     typ_odpowiedzialnosci_skrot='aut.', kolejnosc=None):
        return dodaj_autora(Patent_Autor, self, autor, jednostka, zapisany_jako,
                            typ_odpowiedzialnosci_skrot, kolejnosc)

    class Meta:
        verbose_name = "patent"
        verbose_name_plural = "patenty"
        app_label = 'bpp'

    def __str__(self):
        return self.tytul_oryginalny

    def charakter_formalny(self):
        return Charakter_Formalny.objects.get(skrot="PAT")

    def jezyk(self):
        return Jezyk.objects.get(skrot_dla_pbn="PL")
