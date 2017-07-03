# -*- encoding: utf-8 -*-
from django.contrib.postgres.search import SearchVector
from django.db import models

from bpp.models import BazaModeluOdpowiedzialnosciAutorow, Autor, \
    ModelZRokiem, ModelZeStatusem, ModelZWWW, ModelAfiliowanyRecenzowany, \
    ModelZInformacjaZ, ModelZAdnotacjami, ModelZeSzczegolami, ModelPunktowany
from bpp.models.abstract import ModelPrzeszukiwalny
from bpp.models.util import dodaj_autora, ModelZOpisemBibliograficznym
from django.utils import six

class Patent_Autor(BazaModeluOdpowiedzialnosciAutorow):
    """Powiązanie autora do patentu."""
    rekord = models.ForeignKey('Patent')

    class Meta:
        verbose_name = u'powiązanie autora z patentem'
        verbose_name_plural = u'powiązania autorów z patentami'
        app_label = 'bpp'
        ordering = ('kolejnosc', )
        unique_together = \
            [('rekord', 'autor', 'typ_odpowiedzialnosci'),
              # Tu musi być autor, inaczej admin nie pozwoli wyedytować
             ('rekord', 'autor', 'kolejnosc')]

@six.python_2_unicode_compatible
class Patent(ModelZOpisemBibliograficznym, ModelZRokiem, ModelZeStatusem,
             ModelZWWW, ModelAfiliowanyRecenzowany, ModelPunktowany,
             ModelZeSzczegolami, ModelZInformacjaZ, ModelZAdnotacjami,
             ModelPrzeszukiwalny):

    tytul_oryginalny = models.TextField("Tytuł oryginalny", db_index=True)

    numer = models.CharField(max_length=255, null=True, blank=True)
    z_dnia = models.DateField(null=True, blank=True)
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

