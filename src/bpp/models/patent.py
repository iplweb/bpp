# -*- encoding: utf-8 -*-
from django.db import models
from django.db.models import CASCADE, SET_NULL
from django.db.models.signals import post_delete
from django.dispatch import receiver
from django.utils import six
from django.utils import timezone

from bpp.models import BazaModeluOdpowiedzialnosciAutorow, Autor, \
    ModelZRokiem, ModelZeStatusem, ModelZWWW, ModelRecenzowany, \
    ModelZInformacjaZ, ModelZAdnotacjami, ModelZeSzczegolami, ModelPunktowany, \
    Charakter_Formalny, Jezyk
from bpp.models.abstract import RekordBPPBaza, ModelZAbsolutnymUrl, DodajAutoraMixin, MaProcentyMixin
from bpp.models.util import dodaj_autora


class Patent_Autor(BazaModeluOdpowiedzialnosciAutorow):
    """Powiązanie autora do patentu."""
    rekord = models.ForeignKey('Patent', CASCADE, related_name="autorzy_set")

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
             MaProcentyMixin,
             DodajAutoraMixin,
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
        "bpp.Rodzaj_Prawa_Patentowego", CASCADE,
        null=True, blank=True
    )

    wdrozenie = models.NullBooleanField(
        "Wdrożenie",
    )

    wydzial = models.ForeignKey(
        "bpp.Wydzial", SET_NULL,
        null=True,
        blank=True)

    autor_rekordu_klass = Patent_Autor
    autorzy = models.ManyToManyField(Autor, through=autor_rekordu_klass)

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
