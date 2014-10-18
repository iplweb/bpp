# -*- encoding: utf-8 -*-

"""Funkcje pomocnicze dla klas w bpp.models"""
from django.db import models
from django.core.exceptions import ValidationError
from django.core.urlresolvers import reverse

from django.db.models import Max
from django.template import Template, Context
from django.template.loader import get_template
from django.utils import safestring
from django.conf import settings
from djorm_pgarray.fields import TextArrayField


def dodaj_autora(klass, rekord, autor, jednostka, zapisany_jako=None,
                 typ_odpowiedzialnosci_skrot='aut.', kolejnosc=None):
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

    typ_odpowiedzialnosci = Typ_Odpowiedzialnosci.objects.get_or_create(
        skrot=typ_odpowiedzialnosci_skrot)[0]

    if zapisany_jako is None:
        zapisany_jako = u"%s %s" % (autor.nazwisko, autor.imiona)

    if kolejnosc is None:
        kolejnosc = klass.objects.filter(rekord=rekord).aggregate(
            Max('kolejnosc'))['kolejnosc__max']
        if kolejnosc is None:
            kolejnosc = 1
        else:
            kolejnosc += 1

    return klass.objects.create(
        rekord=rekord, autor=autor, jednostka=jednostka,
        typ_odpowiedzialnosci=typ_odpowiedzialnosci,
        kolejnosc=kolejnosc,
        zapisany_jako=zapisany_jako)


opis_bibliograficzny_template = None
opis_bibliograficzny_komisja_centralna_template = None
opis_bibliograficzny_autorzy_template = None


def renderuj_opis_bibliograficzny(praca):
    """Renderuje opis bibliograficzny dla danej klasy, używając template."""
    global opis_bibliograficzny_template

    if opis_bibliograficzny_template is None:
        opis_bibliograficzny_template = get_template(
            "opis_bibliograficzny/main.html")

    return opis_bibliograficzny_template.render(
        Context(dict(praca=praca))).replace("\r\n", "").replace(
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

    def opis_bibliograficzny(self):
        return renderuj_opis_bibliograficzny(self)

    def opis_bibliograficzny_komisja_centralna(self):
        return renderuj_opis_bibliograficzny_komisja_centralna(self)

    def opis_bibliograficzny_autorzy(self):
        return renderuj_opis_autorow(self)

    opis_bibliograficzny_cache = models.TextField(default='')

    opis_bibliograficzny_autorzy_cache = TextArrayField()

    def zaktualizuj_cache(self, tylko_opis=False):
        self.opis_bibliograficzny_cache = self.opis_bibliograficzny()

        flds = ['opis_bibliograficzny_cache']

        if not tylko_opis:
            if hasattr(self, 'autor'):
                self.opis_bibliograficzny_autorzy_cache = [u"%s %s" % (self.autor.nazwisko, self.autor.imiona)]
            else:
                self.opis_bibliograficzny_autorzy_cache = [x.zapisany_jako for x in self.autorzy.through.objects.filter(rekord=self)]
            flds.append('opis_bibliograficzny_autorzy_cache')

        # Podaj parametr flds aby uniknąć pętli wywoływania sygnału post_save
        self.save(update_fields=flds)

    class Meta:
        abstract = True

class ZapobiegajNiewlasciwymCharakterom(models.Model):
    class Meta:
        abstract = True

    def clean_fields(self, *args, **kw):
        if self.charakter_formalny is not None:
            if self.charakter_formalny.skrot in ['DOK', 'HAB', 'PAT']:
                raise ValidationError({'charakter_formalny': [
                    safestring.mark_safe(u'Jeżeli chcesz dodać rekord o typie "%s"'
                    u', <a href="%s">kliknij tutaj</a>.' % (
                        self.charakter_formalny.nazwa,
                        reverse("admin:bpp_%s_add" % self.charakter_formalny.nazwa.lower().replace(" ", "_"))))]})