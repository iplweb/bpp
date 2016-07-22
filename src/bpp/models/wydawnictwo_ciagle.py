# -*- encoding: utf-8 -*-

from django.db import models
from djorm_pgfulltext.models import SearchManager
from lxml.etree import SubElement, Element
from secure_input.utils import safe_html

from bpp.models.abstract import BazaModeluOdpowiedzialnosciAutorow, DwaTytuly, ModelZRokiem, \
    ModelZWWW, ModelAfiliowanyRecenzowany, ModelPunktowany, ModelTypowany, \
    ModelZeSzczegolami, ModelZInformacjaZ, ModelZeStatusem, ModelZISSN, \
    ModelZAdnotacjami, ModelZCharakterem, Wydawnictwo_Baza, PBNSerializerHelperMixin, ModelZOpenAccess, ModelZPubmedID, \
    ModelZDOI, ModelZeZnakamiWydawniczymi
from bpp.models.util import dodaj_autora, ZapobiegajNiewlasciwymCharakterom


class Wydawnictwo_Ciagle_Autor(BazaModeluOdpowiedzialnosciAutorow):
    """Powiązanie autora do wydawnictwa ciągłego."""
    rekord = models.ForeignKey('Wydawnictwo_Ciagle')

    class Meta:
        verbose_name = u'powiązanie autora z wyd. ciągłym'
        verbose_name_plural = u'powiązania autorów z wyd. ciągłymi'
        app_label = 'bpp'
        ordering = ('kolejnosc', )
        unique_together = \
            [('rekord', 'autor', 'typ_odpowiedzialnosci'),
              # Tu musi być autor, inaczej admin nie pozwoli wyedytować
             ('rekord', 'autor', 'kolejnosc')]


class ModelZOpenAccessWydawnictwoCiagle(ModelZOpenAccess):
    openaccess_tryb_dostepu = models.ForeignKey(
        "Tryb_OpenAccess_Wydawnictwo_Ciagle", verbose_name="OpenAccess: tryb dostępu", blank=True, null=True)

    class Meta:
        abstract = True


class Wydawnictwo_Ciagle(ZapobiegajNiewlasciwymCharakterom,
                         Wydawnictwo_Baza, DwaTytuly, ModelZRokiem,
                         ModelZeStatusem,
                         ModelZWWW, ModelZPubmedID, ModelZDOI, ModelAfiliowanyRecenzowany,
                         ModelPunktowany, ModelTypowany, ModelZeSzczegolami,
                         ModelZISSN, ModelZInformacjaZ, ModelZAdnotacjami,
                         ModelZCharakterem, PBNSerializerHelperMixin,
                         ModelZOpenAccessWydawnictwoCiagle,
                         ModelZeZnakamiWydawniczymi):
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
        verbose_name = u"wydawnictwo ciągłe"
        verbose_name_plural = u"wydawnictwa ciągłe"
        app_label = 'bpp'

    eksport_pbn_FLDS = ["journal", "issue", "volume", "pages", "open-access"]

    def eksport_pbn_journal(self, toplevel, wydzial=None, autorzy_klass=None):
        if self.zrodlo:
            toplevel.append(self.zrodlo.eksport_pbn_serializuj())

    def eksport_pbn_issue(self, toplevel, wydzial=None, autorzy_klass=None):
        if self.informacje.find("nr") >= 0:
            issue = SubElement(toplevel, "issue")
            issue.text = self.informacje.split("nr")[1].strip().split(" ")[0]

    def eksport_pbn_volume(self, toplevel, wydzial=None, autorzy_klass=None):
        if self.informacje.find("vol.") >= 0:
            volume = SubElement(toplevel, 'volume')
            volume.text = self.informacje.split("vol.")[1].strip().split(" ")[0]

    def eksport_pbn_serializuj(self, wydzial):
        toplevel = Element('article')
        super(Wydawnictwo_Ciagle, self).eksport_pbn_serializuj(toplevel, wydzial, Wydawnictwo_Ciagle_Autor)
        self.eksport_pbn_run_serialization_functions(self.eksport_pbn_FLDS, toplevel, wydzial, Wydawnictwo_Ciagle_Autor)
        return toplevel