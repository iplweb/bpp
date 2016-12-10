# -*- encoding: utf-8 -*-
from datetime import datetime
from math import ceil

from dirtyfields.dirtyfields import DirtyFieldsMixin
from django.db import models
from django.db.models.signals import post_delete
from django.utils import timezone
from django.utils.functional import cached_property
from djorm_pgfulltext.models import SearchManager
from lxml.etree import Element, SubElement

from bpp.models.abstract import \
    BazaModeluOdpowiedzialnosciAutorow, DwaTytuly, ModelZRokiem, \
    ModelZWWW, ModelAfiliowanyRecenzowany, ModelPunktowany, ModelTypowany, \
    ModelZeSzczegolami, ModelZInformacjaZ, ModelZeStatusem, ModelZISBN, ModelZAdnotacjami, ModelZCharakterem, \
    Wydawnictwo_Baza, \
    PBNSerializerHelperMixin, ModelZOpenAccess, ModelZPubmedID, ModelZDOI, ModelZeZnakamiWydawniczymi, \
    ModelZAktualizacjaDlaPBN
from bpp.models.autor import Autor
from bpp.models.util import ZapobiegajNiewlasciwymCharakterom
from bpp.models.util import dodaj_autora


class Wydawnictwo_Zwarte_Autor(DirtyFieldsMixin, BazaModeluOdpowiedzialnosciAutorow):
    """Model zawierający informację o przywiązaniu autorów do wydawnictwa
    zwartego."""
    rekord = models.ForeignKey('Wydawnictwo_Zwarte')

    class Meta:
        verbose_name = u'powiązanie autora z wyd. zwartym'
        verbose_name_plural = u'powiązania autorów z wyd. zwartymi'
        app_label = 'bpp'
        ordering = ('kolejnosc',)
        unique_together = \
            [('rekord', 'autor', 'typ_odpowiedzialnosci'),
             # Tu musi być autor, inaczej admin nie pozwoli wyedytować
             ('rekord', 'autor', 'kolejnosc')]

    def save(self, *args, **kw):
        if self.pk is None or self.is_dirty():
            self.rekord.ostatnio_zmieniony_dla_pbn = timezone.now()
            self.rekord.save(update_fields=['ostatnio_zmieniony_dla_pbn'])
        super(Wydawnictwo_Zwarte_Autor, self).save(*args, **kw)


def wydawnictwo_zwarte_autor_post_delete(sender, instance, **kwargs):
    instance.rekord.ostatnio_zmieniony_dla_pbn = timezone.now()
    instance.rekord.save(update_fields=['ostatnio_zmieniony_dla_pbn'])


post_delete.connect(wydawnictwo_zwarte_autor_post_delete, Wydawnictwo_Zwarte_Autor)


class Wydawnictwo_Zwarte_Baza(
    Wydawnictwo_Baza, DwaTytuly, ModelZRokiem, ModelZeStatusem,
    ModelZWWW, ModelZPubmedID, ModelZDOI, ModelAfiliowanyRecenzowany,
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


class ModelZOpenAccessWydawnictwoZwarte(ModelZOpenAccess):
    openaccess_tryb_dostepu = models.ForeignKey("Tryb_OpenAccess_Wydawnictwo_Zwarte", blank=True, null=True)

    class Meta:
        abstract = True


class Wydawnictwo_Zwarte(ZapobiegajNiewlasciwymCharakterom,
                         Wydawnictwo_Zwarte_Baza, ModelZCharakterem,
                         PBNSerializerHelperMixin,
                         ModelZOpenAccessWydawnictwoZwarte,
                         ModelZeZnakamiWydawniczymi,
                         ModelZAktualizacjaDlaPBN,
                         DirtyFieldsMixin):
    """Wydawnictwo zwarte, czyli: książki, broszury, skrypty, fragmenty,
    doniesienia zjazdowe."""

    objects = SearchManager(
        fields=['tytul_oryginalny', 'tytul'],
        config='bpp_nazwy_wlasne')

    autorzy = models.ManyToManyField(Autor, through=Wydawnictwo_Zwarte_Autor)

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

    def eksport_pbn_isbn(self, toplevel, wydzial=None, autorzy_klass=None):
        if self.isbn:
            isbn = SubElement(toplevel, 'isbn')
            isbn.text = self.isbn.replace(".", "").strip()

    def eksport_pbn_publisher_name(self, toplevel, wydzial=None, autorzy_klass=None):
        publisher_name = SubElement(toplevel, 'publisher-name')
        publisher_name.text = self.wydawnictwo

    def eksport_pbn_publication_place(self, toplevel, wydzial=None, autorzy_klass=None):
        if self.miejsce_i_rok:
            try:
                miejsce, rok = self.miejsce_i_rok.split(" ")
            except ValueError:
                miejsce = self.miejsce_i_rok

            if miejsce:
                publication_place = SubElement(toplevel, 'publication-place')
                publication_place.text = miejsce

    def eksport_pbn_size(self, toplevel, wydzial=None, autorzy_klass=None):
        if self.liczba_znakow_wydawniczych:
            size = SubElement(toplevel, 'size', unit="sheets")
            size.text = str(int(ceil(self.liczba_znakow_wydawniczych / 40000.0)))

    def eksport_pbn_book(self, toplevel, wydzial=None, autorzy_klass=None):
        def add_wydawnictwo_nadrzedne_data(book, wydawnictwo_nadrzedne, title_text=None):
            title = SubElement(book, 'title')
            if not title_text:
                title_text = wydawnictwo_nadrzedne.tytul_oryginalny
            title.text = title_text

            publication_date = SubElement(book, 'publication-date')
            publication_date.text = str(wydawnictwo_nadrzedne.rok)

            if wydawnictwo_nadrzedne.isbn:
                isbn = SubElement(book, 'isbn')
                isbn.text = wydawnictwo_nadrzedne.isbn.replace(".", "").strip()

            if wydawnictwo_nadrzedne.wydawnictwo:
                publisher_name = SubElement(book, 'publisher-name')
                publisher_name.text = wydawnictwo_nadrzedne.wydawnictwo

        book = SubElement(toplevel, 'book')

        if self.wydawnictwo_nadrzedne:
            add_wydawnictwo_nadrzedne_data(book, self.wydawnictwo_nadrzedne)

        else:
            add_wydawnictwo_nadrzedne_data(
                book, self,
                title_text=self.informacje.split("W:", 1)[1].strip())

    def eksport_pbn_editor(self, toplevel, wydzial, autorzy_klass):
        from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte_Autor
        if autorzy_klass == Wydawnictwo_Zwarte_Autor:
            for redaktor_wyd in autorzy_klass.objects.filter(
                    rekord=self,
                    typ_odpowiedzialnosci__skrot__in=['red.', 'red. nauk. wyd. pol.']).select_related("jednostka"):
                if redaktor_wyd.jednostka.wydzial_id == wydzial.id:
                    # Afiliowany!
                    toplevel.append(
                        redaktor_wyd.autor.eksport_pbn_serializuj(
                            affiliated=True, employed=redaktor_wyd.zatrudniony, tagname='editor'))

    def eksport_pbn_other_editors(self, toplevel, wydzial, autorzy_klass):
        from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte_Autor
        if autorzy_klass == Wydawnictwo_Zwarte_Autor:
            qry = autorzy_klass.objects.filter(rekord=self, typ_odpowiedzialnosci__skrot__in=['red.', 'red. nauk. wyd. pol.'])

            wszyscy_redaktorzy = qry.count()
            nasi_redaktorzy = qry.filter(jednostka__wydzial_id=wydzial.id).count()

            other_editors = Element('other-editors')
            other_editors.text = str(wszyscy_redaktorzy - nasi_redaktorzy)
            toplevel.append(other_editors)

    eksport_pbn_BOOK_FLDS = ["editor", "isbn", "series", "number-in-series", "edition", "volume", "pages",
                             "publisher-name", "publication-place", "open-access"]
    eksport_pbn_CHAPTER_FLDS = ["editor", "chapter-number", "book", "pages", "open-access"]

    def eksport_pbn_serializuj(self, wydzial):
        toplevel = Element('book')
        flds = self.eksport_pbn_BOOK_FLDS

        if self.is_chapter:
            toplevel = Element('chapter')
            flds = self.eksport_pbn_CHAPTER_FLDS

        super(Wydawnictwo_Zwarte, self).eksport_pbn_serializuj(toplevel, wydzial, Wydawnictwo_Zwarte_Autor)

        self.eksport_pbn_run_serialization_functions(flds, toplevel, wydzial, Wydawnictwo_Zwarte_Autor)

        return toplevel
