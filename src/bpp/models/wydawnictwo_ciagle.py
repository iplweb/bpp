# -*- encoding: utf-8 -*-
import re

from dirtyfields.dirtyfields import DirtyFieldsMixin

from django.db import models
from django.db.models.signals import post_delete
from django.db.utils import DEFAULT_DB_ALIAS
from django.utils import timezone
from lxml.etree import SubElement, Element
from secure_input.utils import safe_html

from bpp.models.abstract import BazaModeluOdpowiedzialnosciAutorow, DwaTytuly, \
    ModelZRokiem, \
    ModelZWWW, ModelAfiliowanyRecenzowany, ModelPunktowany, ModelTypowany, \
    ModelZeSzczegolami, ModelZInformacjaZ, ModelZeStatusem, ModelZISSN, \
    ModelZAdnotacjami, ModelZCharakterem, Wydawnictwo_Baza, \
    PBNSerializerHelperMixin, ModelZOpenAccess, ModelZPubmedID, \
    ModelZDOI, ModelZeZnakamiWydawniczymi, ModelZAktualizacjaDlaPBN
from bpp.models.util import dodaj_autora, ZapobiegajNiewlasciwymCharakterom


class Wydawnictwo_Ciagle_Autor(DirtyFieldsMixin, BazaModeluOdpowiedzialnosciAutorow):
    """Powiązanie autora do wydawnictwa ciągłego."""
    rekord = models.ForeignKey('Wydawnictwo_Ciagle')

    class Meta:
        verbose_name = u'powiązanie autora z wyd. ciągłym'
        verbose_name_plural = u'powiązania autorów z wyd. ciągłymi'
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


parsed_informacje_regex = re.compile(
    r"(\[online\](\s+|)|)(\s+|)"
    r"(?P<rok>\d\d+)\s+"
    r"(((vol|t|r|bd)(\.|) (?P<tom>\d+)|)(\s+|)|)"
    r"(((((nr|z|h)(\.|))) (?P<numer>((\d+)(\w+|))(\/\d+|)))|)",
    flags=re.IGNORECASE)


class Wydawnictwo_Ciagle(ZapobiegajNiewlasciwymCharakterom,
                         Wydawnictwo_Baza, DwaTytuly, ModelZRokiem,
                         ModelZeStatusem,
                         ModelZWWW, ModelZPubmedID, ModelZDOI, ModelAfiliowanyRecenzowany,
                         ModelPunktowany, ModelTypowany, ModelZeSzczegolami,
                         ModelZISSN, ModelZInformacjaZ, ModelZAdnotacjami,
                         ModelZCharakterem, PBNSerializerHelperMixin,
                         ModelZOpenAccessWydawnictwoCiagle,
                         ModelZeZnakamiWydawniczymi,
                         ModelZAktualizacjaDlaPBN,
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
        verbose_name = u"wydawnictwo ciągłe"
        verbose_name_plural = u"wydawnictwa ciągłe"
        app_label = 'bpp'

    eksport_pbn_FLDS = ["journal", "issue", "volume", "pages", "open-access"]

    def eksport_pbn_journal(self, toplevel, wydzial=None, autorzy_klass=None):
        if self.zrodlo:
            toplevel.append(self.zrodlo.eksport_pbn_serializuj())

    def eksport_pbn__get_informacje_by_key(self, key):
        p = parsed_informacje_regex.match(self.informacje)
        if p is not None:
            d = p.groupdict()
            if d.has_key(key):
                return d[key]

    def eksport_pbn_get_issue(self):
        return self.eksport_pbn__get_informacje_by_key("numer")

    def eksport_pbn_issue(self, toplevel, wydzial=None, autorzy_klass=None):
        v = self.eksport_pbn_get_issue()
        issue = SubElement(toplevel, "issue")
        if v is not None:
            issue.text = v
        else:
            issue.text = "brak"

    def eksport_pbn_get_volume(self):
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
