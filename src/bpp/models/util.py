# -*- encoding: utf-8 -*-

"""Funkcje pomocnicze dla klas w bpp.models"""
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError, ObjectDoesNotExist
from django.utils.functional import cached_property

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse
from django.db import models
from django.db.models import Max, TextField
from django.template import Context
from django.template.loader import get_template
from django.utils import safestring


def dodaj_autora(klass, rekord, autor, jednostka, zapisany_jako=None,
                 typ_odpowiedzialnosci_skrot='aut.', kolejnosc=None,
                 dyscyplina_naukowa=None, afiliuje=True):
    """
    Utility function, dodająca autora do danego rodzaju klasy (Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte, Patent); funkcja używana przez te klasy, niejako
    wewnętrzna dla całego API; nie powinna być używana bezpośrednio nigdzie,
    jedynie API tych klas winno być używane.

    :param klass:
    :param rekord:
    :param autor:
    :param jednostka:
    :param zapisany_jako:
    :param typ_odpowiedzialnosci_skrot:
    :param kolejnosc:
    :return:
    """

    from bpp.models import Typ_Odpowiedzialnosci

    typ_odpowiedzialnosci = Typ_Odpowiedzialnosci.objects.get(
        skrot=typ_odpowiedzialnosci_skrot)

    if zapisany_jako is None:
        zapisany_jako = "%s %s" % (autor.nazwisko, autor.imiona)

    if kolejnosc is None:
        kolejnosc = klass.objects.filter(rekord=rekord).aggregate(
            Max('kolejnosc'))['kolejnosc__max']
        if kolejnosc is None:
            kolejnosc = 0
        else:
            kolejnosc += 1

    return klass.objects.create(
        rekord=rekord, autor=autor, jednostka=jednostka,
        typ_odpowiedzialnosci=typ_odpowiedzialnosci,
        kolejnosc=kolejnosc,
        zapisany_jako=zapisany_jako,
        dyscyplina_naukowa=dyscyplina_naukowa,
        afiliuje=afiliuje)


opis_bibliograficzny_template = None
opis_bibliograficzny_komisja_centralna_template = None
opis_bibliograficzny_autorzy_template = None


def renderuj_opis_bibliograficzny(praca, autorzy):
    """Renderuje opis bibliograficzny dla danej klasy, używając template."""
    global opis_bibliograficzny_template

    if opis_bibliograficzny_template is None:
        opis_bibliograficzny_template = get_template(
            "opis_bibliograficzny/main.html")

    return opis_bibliograficzny_template.render(
        dict(praca=praca, autorzy=autorzy)).replace("\r\n", "").replace(
        "\n", "").replace("  ", " ").replace("  ", " ").replace(
        "  ", " ").replace("  ", " ").replace("  ", " ").replace(
        " , ", ", ").replace(" . ", ". ").replace(". . ", ". ").replace(
        ". , ", ". ").replace("., ", ". ").replace(" .", ".").replace(
        ".</b>[", ".</b> [")


def renderuj_opis_bibliograficzny_komisja_centralna(praca):
    global opis_bibliograficzny_komisja_centralna_template

    if opis_bibliograficzny_komisja_centralna_template is None:
        opis_bibliograficzny_komisja_centralna_template = get_template(
            "opis_bibliograficzny/main-komisja-centralna.html")

    return opis_bibliograficzny_komisja_centralna_template.render(
        Context(dict(praca=praca)))


def renderuj_opis_autorow(praca):
    global opis_bibliograficzny_autorzy_template
    if opis_bibliograficzny_autorzy_template is None:
        opis_bibliograficzny_autorzy_template = get_template(
            "opis_bibliograficzny/autorzy.html")
    return opis_bibliograficzny_autorzy_template.render(
        Context(dict(praca=praca)))


class ModelZOpisemBibliograficznym(models.Model):
    """Mixin, umożliwiający renderowanie opisu bibliograficznego dla danego
    obiektu przy pomocy template."""

    def opis_bibliograficzny(self, autorzy=None):
        if autorzy is None:
            autorzy = self.autorzy_dla_opisu()
        return renderuj_opis_bibliograficzny(self, autorzy)

    def opis_bibliograficzny_komisja_centralna(self):
        return renderuj_opis_bibliograficzny_komisja_centralna(self)

    def opis_bibliograficzny_autorzy(self):
        return renderuj_opis_autorow(self)

    tekst_przed_pierwszym_autorem = models.TextField(blank=True, null=True)
    tekst_po_ostatnim_autorze = models.TextField(blank=True, null=True)

    opis_bibliograficzny_cache = models.TextField(default='')

    # To pole używane jest na ten moment jedynie przez moduł OAI, do szybkiego
    # produkowania pola "Creator" dla formatu Dublin Core, vide moduł bpp.oai .
    # To pole zawiera listę autorów, w kolejności, nazwisko i imię, bez
    # tytułu
    opis_bibliograficzny_autorzy_cache = ArrayField(TextField(), blank=True,
                                                    null=True)

    # To pole używane jest przez Raport autorów oraz Raport jednostek do wypluwania
    # listy zapisanych nazwisk
    opis_bibliograficzny_zapisani_autorzy_cache = models.TextField(default='')

    def autorzy_dla_opisu(self):
        # takie 'autorzy_set.all()' tylko na potrzeby opisu bibliograficznego
        return self.autorzy_set.select_related("autor", "typ_odpowiedzialnosci").order_by('kolejnosc')

    def zaktualizuj_cache(self, tylko_opis=False):

        flds = []

        autorzy = self.autorzy_dla_opisu()
        opis = self.opis_bibliograficzny(autorzy)

        if self.opis_bibliograficzny_cache != opis:
            self.opis_bibliograficzny_cache = opis
            flds = ['opis_bibliograficzny_cache']

        if not tylko_opis:

            if hasattr(self, 'autor'):
                zapisani = ["%s %s" % (autorzy[0].autor.nazwisko, autorzy[0].autor.imiona)]
            else:
                zapisani = [x.zapisany_jako for x in autorzy]

            oac = ["%s %s" % (x.autor.nazwisko, x.autor.imiona) for x in autorzy]
            if self.opis_bibliograficzny_autorzy_cache != oac:
                self.opis_bibliograficzny_autorzy_cache = oac
                flds.append('opis_bibliograficzny_autorzy_cache')

            ozac = ", ".join(zapisani)
            if self.opis_bibliograficzny_zapisani_autorzy_cache != ozac:
                self.opis_bibliograficzny_zapisani_autorzy_cache = ozac
                flds.append('opis_bibliograficzny_zapisani_autorzy_cache')

        # Podaj parametr flds aby uniknąć pętli wywoływania sygnału post_save
        if flds:
            self.save(update_fields=flds)

    class Meta:
        abstract = True


class ZapobiegajNiewlasciwymCharakterom(models.Model):
    class Meta:
        abstract = True

    def clean_fields(self, *args, **kw):
        try:
            cf = self.charakter_formalny
        except ObjectDoesNotExist:
            cf = None

        if cf is not None:
            if self.charakter_formalny.skrot in ['D', 'H', 'PAT']:
                raise ValidationError({'charakter_formalny': [
                    safestring.mark_safe('Jeżeli chcesz dodać rekord o typie "%s"'
                                         ', <a href="%s">kliknij tutaj</a>.' % (
                                             self.charakter_formalny.nazwa,
                                             reverse(
                                                 "admin:bpp_%s_add" % self.charakter_formalny.nazwa.lower().replace(" ",
                                                                                                                    "_"))))]})
