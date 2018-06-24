# -*- encoding: utf-8 -*-
import re

from dirtyfields.dirtyfields import DirtyFieldsMixin
from django.db import models
from django.db.models.signals import post_delete
from django.utils import timezone
from django.utils.functional import cached_property
from lxml.etree import Element, SubElement

from bpp.models import TO_AUTOR
from bpp.models.abstract import \
    BazaModeluOdpowiedzialnosciAutorow, DwaTytuly, ModelZRokiem, \
    ModelZWWW, ModelRecenzowany, ModelPunktowany, ModelTypowany, \
    ModelZeSzczegolami, ModelZInformacjaZ, ModelZeStatusem, ModelZISBN, \
    ModelZAdnotacjami, ModelZCharakterem, \
    Wydawnictwo_Baza, \
    PBNSerializerHelperMixin, ModelZOpenAccess, ModelZPubmedID, ModelZDOI, \
    ModelZeZnakamiWydawniczymi, \
    ModelZAktualizacjaDlaPBN, ModelZKonferencja, \
    ModelZSeria_Wydawnicza, ModelZISSN, ModelWybitny, ModelZAbsolutnymUrl, ModelZLiczbaCytowan
from bpp.models.autor import Autor
from bpp.models.const import TO_REDAKTOR
from bpp.models.util import ZapobiegajNiewlasciwymCharakterom
from bpp.models.util import dodaj_autora


class Wydawnictwo_Zwarte_Autor(DirtyFieldsMixin, BazaModeluOdpowiedzialnosciAutorow):
    """Model zawierający informację o przywiązaniu autorów do wydawnictwa
    zwartego."""
    rekord = models.ForeignKey('Wydawnictwo_Zwarte', related_name="autorzy_set")

    class Meta:
        verbose_name = 'powiązanie autora z wyd. zwartym'
        verbose_name_plural = 'powiązania autorów z wyd. zwartymi'
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
        super(Wydawnictwo_Zwarte_Autor, self).save(*args, **kw)


def wydawnictwo_zwarte_autor_post_delete(sender, instance, **kwargs):
    instance.rekord.ostatnio_zmieniony_dla_pbn = timezone.now()
    instance.rekord.save(update_fields=['ostatnio_zmieniony_dla_pbn'])


post_delete.connect(wydawnictwo_zwarte_autor_post_delete, Wydawnictwo_Zwarte_Autor)

MIEJSCE_I_ROK_MAX_LENGTH = 256

class Wydawnictwo_Zwarte_Baza(
    Wydawnictwo_Baza, DwaTytuly, ModelZRokiem, ModelZeStatusem,
    ModelZWWW, ModelZPubmedID, ModelZDOI, ModelRecenzowany,
    ModelPunktowany, ModelTypowany, ModelZeSzczegolami,
    ModelZInformacjaZ, ModelZISBN, ModelZAdnotacjami, ModelZAbsolutnymUrl,
    ModelZLiczbaCytowan):
    """Baza dla klas Wydawnictwo_Zwarte oraz Praca_Doktorska_Lub_Habilitacyjna
    """

    miejsce_i_rok = models.CharField(
        max_length=MIEJSCE_I_ROK_MAX_LENGTH,
        blank=True, null=True, help_text="""Przykładowo:
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


rok_regex = re.compile(r"\s[12]\d\d\d")


class Wydawnictwo_Zwarte(ZapobiegajNiewlasciwymCharakterom,
                         Wydawnictwo_Zwarte_Baza, ModelZCharakterem,
                         PBNSerializerHelperMixin,
                         ModelZOpenAccessWydawnictwoZwarte,
                         ModelZeZnakamiWydawniczymi,
                         ModelZAktualizacjaDlaPBN,
                         ModelZKonferencja,
                         ModelZSeria_Wydawnicza,
                         ModelZISSN,
                         ModelWybitny,
                         DirtyFieldsMixin):
    """Wydawnictwo zwarte, czyli: książki, broszury, skrypty, fragmenty,
    doniesienia zjazdowe."""

    autorzy = models.ManyToManyField(Autor, through=Wydawnictwo_Zwarte_Autor)

    wydawnictwo_nadrzedne = models.ForeignKey(
        'self', blank=True, null=True, help_text="""Jeżeli dodajesz rozdział,
        tu wybierz pracę, w ramach której dany rozdział występuje.""",
        related_name="wydawnictwa_powiazane_set")

    calkowita_liczba_autorow = models.PositiveIntegerField(
        blank=True, null=True, help_text="""Jeżeli dodajesz monografię, wpisz 
        tutaj całkowitą liczbę autorów monografii. Ta informacja zostanie 
        użyta w eksporcie danych do PBN. Jeżeli informacja ta nie zostanie 
        uzupełiona, wartość tego pola zostanie obliczona i będzie to ilość 
        wszystkich autorów przypisanych do danej monografii"""
    )

    calkowita_liczba_redaktorow = models.PositiveIntegerField(
        blank=True, null=True, help_text="""Jeżeli dodajesz monografię, wpisz tutaj całkowitą liczbę
        redaktorów monografii. Ta informacja zostanie użyta w eksporcie 
        danych do PBN. Jeżeli pole to nie zostanie uzupełnione, wartość ta
        zostanie obliczona i będzie to ilość wszystkich redaktorów 
        przypisanych do danej monografii"""
    )

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
        return self.charakter_formalny.rozdzial_pbn

    @cached_property
    def is_book(self):
        return self.charakter_formalny.ksiazka_pbn

    def eksport_pbn_isbn(self, toplevel, wydzial=None, autorzy_klass=None):
        if self.isbn:
            isbn = SubElement(toplevel, 'isbn')
            isbn.text = self.isbn.replace(".", "").strip()

    def eksport_pbn_issn(self, toplevel, wydzial=None, autorzy_klass=None):
        if self.issn:
            issn = SubElement(toplevel, 'issn')
            issn.text = self.issn.replace(".", "").strip()

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
                publication_place.text = rok_regex.sub("", miejsce.strip()).strip()

    def eksport_pbn_size(self, toplevel, wydzial=None, autorzy_klass=None):
        if self.ma_wymiar_wydawniczy():
            size = SubElement(toplevel, 'size', unit="sheets")
            size.text = self.wymiar_wydawniczy_w_arkuszach()

    def eksport_pbn_series(self, toplevel, wydzial=None, autorzy_klass=None):
        if self.seria_wydawnicza is not None:
            series = SubElement(toplevel, 'series')
            series.text = self.seria_wydawnicza.nazwa

    def eksport_pbn_number_in_series(self, toplevel, wydzial=None,
                                     autorzy_klass=None):
        if self.numer_w_serii is not None:
            tag = SubElement(toplevel, 'number-in-series')
            tag.text = str(self.numer_w_serii)


    def eksport_pbn_book(self, toplevel, wydzial, autorzy_klass=None):
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
            self.wydawnictwo_nadrzedne.eksport_pbn_serializuj(wydzial=wydzial, toplevel=book)

        else:
            title_text = None
            try:
                title_text = self.informacje.split("W:", 1)[1].strip()
            except IndexError:
                pass

            if title_text:
                add_wydawnictwo_nadrzedne_data(book, self, title_text=title_text)

    def eksport_pbn_editor(self, toplevel, wydzial, autorzy_klass):
        from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte_Autor
        if autorzy_klass == Wydawnictwo_Zwarte_Autor:
            for redaktor_wyd in autorzy_klass.objects.filter(
                    rekord=self,
                    typ_odpowiedzialnosci__typ_ogolny=TO_REDAKTOR).select_related("jednostka"):
                if redaktor_wyd.jednostka.wydzial_id == wydzial.id:
                    # Afiliowany!
                    toplevel.append(
                        redaktor_wyd.autor.eksport_pbn_serializuj(
                            affiliated=redaktor_wyd.afiliuje,
                            employed=redaktor_wyd.zatrudniony,
                            tagname='editor'))

    def eksport_pbn_other_editors(self, toplevel, wydzial, autorzy_klass):
        from bpp.models.wydawnictwo_zwarte import Wydawnictwo_Zwarte_Autor
        if autorzy_klass == Wydawnictwo_Zwarte_Autor:
            wszyscy_redaktorzy = self.calkowita_liczba_redaktorow

            qry = autorzy_klass.objects.filter(
                rekord=self,
                typ_odpowiedzialnosci__typ_ogolny=TO_REDAKTOR
            )

            if wszyscy_redaktorzy is None:
                wszyscy_redaktorzy = qry.count()

            nasi_redaktorzy = qry.filter(jednostka__wydzial_id=wydzial.id).count()

            other_editors = Element('other-editors')
            other_editors.text = str(wszyscy_redaktorzy - nasi_redaktorzy)
            toplevel.append(other_editors)

    #
    # def eksport_pbn_get_autorzy_iter(self, wydzial, autorzy_klass):
    #     # Jeżeli KSIĄŻKA ma jakiekolwiek wydawnictwa POWIĄZANE, to wyrzuć tutaj WSZYSTKICH AUTORÓW
    #     # przypisanych do jednostek znajdujących się w danym WYDZIALE dla tych powiązanych REKORDÓW.
    #     if not self.is_chapter:
    #         raise NotImplementedError
    #
    #     # Jeżeli nie ma, to standardowo:
    #     return super(Wydawnictwo_Zwarte, self).eksport_pbn_get_autorzy_iter(self, wydzial, autorzy_klass)
    #
    #
    # def eksport_pbn_get_other_contributors_cnt(self, wydzial, autorzy_klass):
    #     # Jeżeli KSIĄŻKA ma jakiekolwiek wydawnictwa POWIĄZANE, to poczli tutaj WSZYSTKICH AUTORÓW
    #     # OPRÓCZ przypisanych do jednostek znajdujących się w danym WYDZIALE dla tych powiązanych REKORDÓW.
    #     if not self.is_chapter:
    #         if self.wydawnictwa_powiazane_set.count():
    #             autorzy_klass.objects.
    #             raise NotImplementedError
    #
    #     # Jeżeli nie jest to książką, to standardowo:
    #     super(Wydawnictwo_Zwarte, self).eksport_pbn_get_other_contributors_cnt(wydzial, autorzy_klass)

    def eksport_pbn_get_nasi_autorzy_iter(self, wydzial, autorzy_klass):
        # TODO: zrób sprawdzanie jednostki w kontekście ROKU do jakiego wydziału była WÓWCZAS przypisana

        ret = set()

        if self.is_book:
            autorzy_powiazanych = autorzy_klass.objects.filter(
                    rekord__in=self.wydawnictwa_powiazane_set.all().values_list("pk", flat=True),
                    typ_odpowiedzialnosci__typ_ogolny=TO_AUTOR).select_related("jednostka")

            for elem in autorzy_powiazanych:
                if elem.jednostka.wydzial_id == wydzial.pk and elem.autor_id not in ret:
                    ret.add(elem.autor_id)
                    yield elem

            autorzy_tego = autorzy_klass.objects.filter(
                rekord=self,
                typ_odpowiedzialnosci__typ_ogolny=TO_AUTOR).select_related('jednostka')

            for elem in autorzy_tego:
                if elem.jednostka.wydzial_id == wydzial.pk and elem.autor_id not in ret:
                    ret.add(elem.autor_id)
                    yield elem
        else:
            for elem in super(Wydawnictwo_Zwarte, self).eksport_pbn_get_nasi_autorzy_iter(wydzial, autorzy_klass):
                yield elem

    def eksport_pbn_get_wszyscy_autorzy_iter(self, wydzial, autorzy_klass):
        ret = set()

        if self.is_book:
            for elem in autorzy_klass.objects.filter(
                    rekord__in=self.wydawnictwa_powiazane_set.all().values_list("pk", flat=True),
                    typ_odpowiedzialnosci__typ_ogolny=TO_AUTOR):
                if elem.autor_id not in ret:
                    ret.add(elem.autor_id)
                    yield elem

            for elem in autorzy_klass.objects.filter(
                    rekord=self,
                    typ_odpowiedzialnosci__typ_ogolny=TO_AUTOR):
                if elem.autor_id not in ret:
                    ret.add(elem.autor_id)
                    yield elem

        else:
            for elem in super(Wydawnictwo_Zwarte, self).eksport_pbn_get_wszyscy_autorzy_iter(wydzial, autorzy_klass):
                yield elem

    def eksport_pbn_get_wszyscy_autorzy_count(self, wydzial, autorzy_klass):
        if self.is_book:
            wszyscy_autorzy = self.calkowita_liczba_autorow
            if wszyscy_autorzy is None:
                wszyscy_autorzy = len(list(self.eksport_pbn_get_wszyscy_autorzy_iter(wydzial, autorzy_klass)))
            return wszyscy_autorzy
        return super(Wydawnictwo_Zwarte, self).eksport_pbn_get_wszyscy_autorzy_count(wydzial, autorzy_klass)

    eksport_pbn_BOOK_FLDS = ["editor",
                             "isbn",
                             "issn",
                             "series",
                             "number-in-series",
                             "edition",
                             "volume",
                             "pages",
                             "publisher-name",
                             "publication-place",
                             "open-access"]

    eksport_pbn_CHAPTER_FLDS = ["editor",
                                "chapter-number",
                                "book",
                                "pages",
                                "open-access"]

    def eksport_pbn_serializuj(self, wydzial, toplevel=None):
        if toplevel is None:
            my_toplevel = Element('book')
        flds = self.eksport_pbn_BOOK_FLDS

        if self.is_chapter:
            if toplevel is None:
                my_toplevel = Element('chapter')
            flds = self.eksport_pbn_CHAPTER_FLDS

        if toplevel is None:
            toplevel = my_toplevel

        super(Wydawnictwo_Zwarte, self).eksport_pbn_serializuj(toplevel, wydzial, Wydawnictwo_Zwarte_Autor)
        self.eksport_pbn_run_serialization_functions(flds, toplevel, wydzial, Wydawnictwo_Zwarte_Autor)
        return toplevel

