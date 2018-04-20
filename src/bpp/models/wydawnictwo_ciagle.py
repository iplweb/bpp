# -*- encoding: utf-8 -*-

from dirtyfields.dirtyfields import DirtyFieldsMixin
from django.db import models
from django.db.models.signals import post_delete
from django.utils import timezone
from lxml.etree import SubElement, Element
from secure_input.utils import safe_html

from bpp.models.abstract import BazaModeluOdpowiedzialnosciAutorow, DwaTytuly, \
    ModelZRokiem, \
    ModelZWWW, ModelRecenzowany, ModelPunktowany, ModelTypowany, \
    ModelZeSzczegolami, ModelZInformacjaZ, ModelZeStatusem, ModelZISSN, \
    ModelZAdnotacjami, ModelZCharakterem, Wydawnictwo_Baza, \
    PBNSerializerHelperMixin, ModelZOpenAccess, ModelZPubmedID, \
    ModelZDOI, ModelZeZnakamiWydawniczymi, ModelZAktualizacjaDlaPBN, \
    parse_informacje, ModelZNumeremZeszytu, ModelZKonferencja, ModelWybitny, \
    ModelZAbsolutnymUrl, ModelZLiczbaCytowan
from bpp.models.system import Zewnetrzna_Baza_Danych
from bpp.models.util import dodaj_autora, ZapobiegajNiewlasciwymCharakterom


class Wydawnictwo_Ciagle_Autor(DirtyFieldsMixin, BazaModeluOdpowiedzialnosciAutorow):
    """Powiązanie autora do wydawnictwa ciągłego."""
    rekord = models.ForeignKey('Wydawnictwo_Ciagle', related_name="autorzy_set")

    class Meta:
        verbose_name = 'powiązanie autora z wyd. ciągłym'
        verbose_name_plural = 'powiązania autorów z wyd. ciągłymi'
        app_label = 'bpp'
        ordering = ('kolejnosc',)
        unique_together = \
            [('rekord', 'autor', 'typ_odpowiedzialnosci'),
             # Tu musi być autor, inaczej admin nie pozwoli wyedytować
             ('rekord', 'autor', 'kolejnosc')]

    def save(self, *args, **kw):
        if self.pk is None or self.is_dirty():
            # W sytuacji gdy dodajemy nowego autora lub zmieniamy jego dane,
            # rekord "nadrzędny" publikacji powinien mieć zaktualizowany
            # czas ostatniej aktualizacji na potrzeby PBN:
            r = self.rekord
            r.ostatnio_zmieniony_dla_pbn = timezone.now()
            r.save(update_fields=['ostatnio_zmieniony_dla_pbn'])
        super(Wydawnictwo_Ciagle_Autor, self).save(*args, **kw)


def wydawnictwo_ciagle_autor_post_delete(sender, instance, **kwargs):
    rec = instance.rekord
    rec.ostatnio_zmieniony_dla_pbn = timezone.now()
    rec.save(update_fields=['ostatnio_zmieniony_dla_pbn'])


post_delete.connect(wydawnictwo_ciagle_autor_post_delete, Wydawnictwo_Ciagle_Autor)


class ModelZOpenAccessWydawnictwoCiagle(ModelZOpenAccess):
    openaccess_tryb_dostepu = models.ForeignKey(
        "Tryb_OpenAccess_Wydawnictwo_Ciagle", verbose_name="OpenAccess: tryb dostępu", blank=True, null=True)

    class Meta:
        abstract = True


class Wydawnictwo_Ciagle(ZapobiegajNiewlasciwymCharakterom,
                         Wydawnictwo_Baza, DwaTytuly, ModelZRokiem,
                         ModelZeStatusem, ModelZAbsolutnymUrl,
                         ModelZWWW, ModelZPubmedID, ModelZDOI, ModelRecenzowany,
                         ModelPunktowany, ModelTypowany, ModelZeSzczegolami,
                         ModelZISSN, ModelZInformacjaZ, ModelZAdnotacjami,
                         ModelZCharakterem, PBNSerializerHelperMixin,
                         ModelZOpenAccessWydawnictwoCiagle,
                         ModelZeZnakamiWydawniczymi,
                         ModelZAktualizacjaDlaPBN,
                         ModelZNumeremZeszytu,
                         ModelZKonferencja,
                         ModelWybitny,
                         ModelZLiczbaCytowan,
                         DirtyFieldsMixin):
    """Wydawnictwo ciągłe, czyli artykuły z czasopism, komentarze, listy
    do redakcji, publikacje w suplemencie, etc. """

    autorzy = models.ManyToManyField('Autor', through=Wydawnictwo_Ciagle_Autor)

    zrodlo = models.ForeignKey('Zrodlo', null=True, verbose_name="Źródło", on_delete=models.SET_NULL)

    # To pole nie służy w bazie danych do niczego - jedyne co, to w adminie
    # w wygodny sposób chcemy wyświetlić przycisk 'uzupelnij punktacje', jak
    # się okazuje, przy używaniu standardowych procedur w Django jest to
    # z tego co na dziś dzień umiem, mocno utrudnione.
    uzupelnij_punktacje = models.BooleanField(default=False)

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

    eksport_pbn_FLDS = ["journal", "issue", "volume", "pages", "open-access"]

    def eksport_pbn_journal(self, toplevel, wydzial=None, autorzy_klass=None):
        if self.zrodlo:
            toplevel.append(self.zrodlo.eksport_pbn_serializuj())

    def eksport_pbn__get_informacje_by_key(self, key):
        return parse_informacje(self.informacje, key)

    def eksport_pbn_get_issue(self):
        if hasattr(self, "nr_zeszytu"):
            if self.nr_zeszytu:
                return self.nr_zeszytu
        return self.eksport_pbn__get_informacje_by_key("numer")

    def eksport_pbn_issue(self, toplevel, wydzial=None, autorzy_klass=None):
        v = self.eksport_pbn_get_issue()
        issue = SubElement(toplevel, "issue")
        if v is not None:
            issue.text = v
        else:
            issue.text = "brak"

    def eksport_pbn_get_volume(self):
        if hasattr(self, "tom"):
            if self.tom:
                return self.tom
        return self.eksport_pbn__get_informacje_by_key("tom")

    def eksport_pbn_volume(self, toplevel, wydzial=None, autorzy_klass=None):
        v = self.eksport_pbn_get_volume()
        volume = SubElement(toplevel, "volume")
        if v is not None:
            volume.text = v
        else:
            volume.text = "brak"

    def eksport_pbn_serializuj(self, wydzial):
        toplevel = Element('article')
        super(Wydawnictwo_Ciagle, self).eksport_pbn_serializuj(toplevel, wydzial, Wydawnictwo_Ciagle_Autor)
        self.eksport_pbn_run_serialization_functions(self.eksport_pbn_FLDS, toplevel, wydzial, Wydawnictwo_Ciagle_Autor)
        return toplevel


class Wydawnictwo_Ciagle_Zewnetrzna_Baza_Danych(models.Model):
    rekord = models.ForeignKey(Wydawnictwo_Ciagle)
    baza = models.ForeignKey(Zewnetrzna_Baza_Danych)
    info = models.CharField(
        verbose_name="Informacje dodatkowe",
        max_length=512,
        blank=True,
        null=True)

    class Meta:
        verbose_name = "powiązanie wydawnictwa ciągłego z zewnętrznymi bazami danych"
        verbose_name_plural = "powiązania wydawnictw ciągłych z zewnętrznymi bazami danych"
