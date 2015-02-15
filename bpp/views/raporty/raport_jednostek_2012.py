# -*- encoding: utf-8 -*-

from decimal import Decimal
from django.core.exceptions import ObjectDoesNotExist
from django.utils.datastructures import SortedDict
from django.utils.safestring import mark_safe
from django.views.generic import DetailView
from django_tables2 import RequestConfig, A, Column, Table

import itertools
import sys

from bpp.models import Jednostka, Charakter_Formalny, Jezyk, \
    Typ_Odpowiedzialnosci, Wydawnictwo_Zwarte_Autor
from bpp.models.cache import Rekord, Autorzy


class SumyImpactKbnMixin:
    sum_impact = Decimal('0.0')
    sum_punkty_kbn = Decimal('0.0')

    impact_factor = Column("IF")
    punkty_kbn = Column("PK (MNiSzW)")

    def render_impact_factor(self, record):
        self.sum_impact += record.impact_factor
        return record.impact_factor

    def render_punkty_kbn(self, record):
        self.sum_punkty_kbn += record.punkty_kbn
        return record.punkty_kbn


class TypowaTabelaMixin:
    lp = Column("Lp.", A("id"), empty_values=(), orderable=False)
    tytul_oryginalny = Column("Tytuł")
    jezyk = Column("Język", A("jezyk.skrot"), orderable=False)
    autorzy = Column(
        "Autor (autorzy)",
        A('opis_bibliograficzny_autorzy_cache'),
        orderable=False)

    def __init__(self):
        self.counter = 0

    def render_lp(self, record):
        self.counter += 1
        return '%d.' % self.counter

    def render_autorzy(self, record):
        return ", ".join(record.opis_bibliograficzny_autorzy_cache)

    def render_tytul_oryginalny(self, record):
        return mark_safe(record.tytul_oryginalny)


class Tabela_Publikacji(TypowaTabelaMixin, SumyImpactKbnMixin, Table):
    class Meta:
        attrs = {"class": "paleblue"}
        template = "raporty/raport_jednostek_2012/publikacje.html"
        per_page = sys.maxint
        empty_text = "Brak takich rekordów."
        sequence = ('lp', 'zrodlo', 'lp_art', 'autorzy', 'tytul_oryginalny',
                    'jezyk', 'rok', 'impact_factor', 'punkty_kbn')

    lp = TypowaTabelaMixin.lp
    autorzy = TypowaTabelaMixin.autorzy
    tytul_oryginalny = TypowaTabelaMixin.tytul_oryginalny
    jezyk = TypowaTabelaMixin.jezyk
    impact_factor = SumyImpactKbnMixin.impact_factor
    punkty_kbn = SumyImpactKbnMixin.punkty_kbn

    zrodlo = Column("Czasopismo", A("zrodlo.nazwa"), orderable=False)
    lp_art = Column("Lp. art.", A("id"), empty_values=(), orderable=False)
    rok = Column("Rok, tom, zakres stron", orderable=False)

    def __init__(self, *args, **kwargs):
        Table.__init__(self, *args, **kwargs)
        TypowaTabelaMixin.__init__(self)
        self.zrodlo_counter = itertools.count(1)
        self.output_zrodlo = False
        self.old_zrodlo = None

    def render_lp_art(self, record):
        ret = "%s.%s." % (self.counter, next(self.zrodlo_counter))
        return ret

    def render_lp(self, record):
        # record.zrodlo moze byc None
        try:
            new_zrodlo = record.zrodlo.nazwa
        except ObjectDoesNotExist:
            new_zrodlo = u''

        if self.old_zrodlo != new_zrodlo:
            self.counter += 1
            self.zrodlo_counter = itertools.count(1)
            self.old_zrodlo = new_zrodlo
            self.nowe_zrodlo_w_wierszu = True
        else:
            self.nowe_zrodlo_w_wierszu = False

        if self.nowe_zrodlo_w_wierszu:
            return '%d.' % self.counter
        return u''

    def render_zrodlo(self, record):
        if self.nowe_zrodlo_w_wierszu:
            return record.zrodlo.nazwa

        return u''

    def render_rok(self, record):
        buf = record.szczegoly
        if record.uwagi:
            buf += u", " + record.uwagi
        return buf


class Tabela_Monografii(TypowaTabelaMixin, SumyImpactKbnMixin, Table):
    class Meta:
        attrs = {"class": "paleblue"}
        template = "raporty/raport_jednostek_2012/monografie.html"
        per_page = sys.maxint
        empty_text = "Brak takich rekordów."
        sequence = ('lp', 'autorzy', 'wydawca', 'tytul_oryginalny',
                    'jezyk', 'rok', 'punkty_kbn')

    lp = TypowaTabelaMixin.lp
    autorzy = TypowaTabelaMixin.autorzy
    tytul_oryginalny = TypowaTabelaMixin.tytul_oryginalny
    jezyk = TypowaTabelaMixin.jezyk
    impact_factor = SumyImpactKbnMixin.impact_factor
    punkty_kbn = SumyImpactKbnMixin.punkty_kbn

    wydawca = Column("Wydawca", A("wydawnictwo"), orderable=False)
    rok = Column("Rok", orderable=False)

    def __init__(self, *args, **kwargs):
        Table.__init__(self, *args, **kwargs)
        TypowaTabelaMixin.__init__(self)


def split_red(s, want, if_no_result=None):
    seps = [u"Pod. red.", u"Pod red.", u"Red. nauk.",
            u"red.", u"Pod redakcją", u"pod redakcją",
            u"Red.", u"Ed. by"]

    for sep in seps:
        if s.find(sep) > 0:
            x = s.split(sep)
            if len(x) > want:
                return x[want]

    if if_no_result:
        return if_no_result

    return s


class Tabela_Rozdzialu_Monografii(TypowaTabelaMixin, SumyImpactKbnMixin, Table):
    class Meta:
        attrs = {"class": "paleblue"}
        template = "raporty/raport_jednostek_2012/rozdzialy_monografii.html"
        per_page = sys.maxint
        empty_text = "Brak takich rekordów."
        sequence = ('lp', 'autorzy', 'wydawca', 'tytul',
                    'tytul_rozdzialu', 'jezyk', 'rok',
                    'impact_factor', # redaktor monografii
                    'punkty_kbn')

    lp = TypowaTabelaMixin.lp
    autorzy = TypowaTabelaMixin.autorzy

    tytul = Column("Tytuł monografii", A("pk"))
    tytul_rozdzialu = Column("Tytuł rozdziału", A("tytul_oryginalny"))

    jezyk = TypowaTabelaMixin.jezyk
    punkty_kbn = SumyImpactKbnMixin.punkty_kbn

    wydawca = Column("Wydawca", A("wydawnictwo"), orderable=False)
    impact_factor  = Column("Redaktor monografii")
    rok = Column("Rok", orderable=False)

    def __init__(self, *args, **kwargs):
        Table.__init__(self, *args, **kwargs)
        TypowaTabelaMixin.__init__(self)

    def render_tytul(self, record):
        # JEŻĘLI ma zdefiniowaną monografię NADRZĘDNĄ to ją wyrzuć tutaj
        orig = record.original

        if hasattr(orig, 'wydawnictwo_nadrzedne'):
            wn = orig.wydawnictwo_nadrzedne
            if wn is not None:
                return wn.tytul_oryginalny

        return split_red(record.informacje, 0, if_no_result="").replace("W: ", "")

    def render_tytul_rozdzialu(self, record):
        return record.tytul_oryginalny

    def render_impact_factor(self, record): # redaktor monografii
        orig = record.original

        if hasattr(orig, 'wydawnictwo_nadrzedne'):
            wn = orig.wydawnictwo_nadrzedne
            if wn is not None:
                redaktorzy = Wydawnictwo_Zwarte_Autor.objects.filter(
                    rekord=wn,
                    typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.get(
                        skrot='red.'))

                return u", ".join([unicode(red) for red in redaktorzy])

        return split_red(record.informacje, 1, "").strip(" .")


def wiele(model, *args):
    return [model.objects.get(skrot=x) for x in args]


def charaktery(*args):
    return wiele(Charakter_Formalny, *args)


def jezyki(*args):
    return wiele(Jezyk, *args)


def jezyki_obce():
    return jezyki('ang.', 'niem.', 'fr.', 'hiszp.', 'ros.', 'wł.')

WSZYSTKIE_TABELE = SortedDict(
    [
        ("1_1", Tabela_Publikacji),
        ("1_2", Tabela_Publikacji),
        ("1_3", Tabela_Publikacji),
        ("1_4", Tabela_Publikacji), # Tabela_Konferencji_Miedzynarodowej),
        ("2_1", Tabela_Monografii),
        ("2_2", Tabela_Monografii),
        ("2_3", Tabela_Rozdzialu_Monografii),
        ("2_4", Tabela_Rozdzialu_Monografii),
        ("2_5", Tabela_Monografii),
        ("2_6", Tabela_Monografii),
    ])


def raport_jednostek_tabela(key, base_query, jednostka):
    if key == "1_1":
        return base_query.filter(
            impact_factor__gt=0,
            punktacja_wewnetrzna=0).order_by("zrodlo__nazwa")

    elif key == "1_2":
        return base_query.filter(
            charakter_formalny__skrot="AC",
            impact_factor=0,
            punkty_kbn__gt=0)

    elif key == "1_3":
        return base_query.filter(
            charakter_formalny__skrot="AC",
            uwagi__icontains='erih',
            punkty_kbn__in=[10, 12, 14])

    elif key == "1_4":
        return base_query.filter(
            charakter_formalny__in=charaktery(
                'ZRZ', 'PRZ', 'PSZ', 'ZSZ'),
            punkty_kbn=10)

    elif key == "2_1":
        return base_query.filter(
            charakter_formalny=Charakter_Formalny.objects.get(skrot='KSZ'),
            jezyk__in=jezyki_obce(),
            # znajdz autorow w jednostce
            original__in_raw=Autorzy.objects.filter(
                jednostka_id=jednostka.pk,
                typ_odpowiedzialnosci_id=Typ_Odpowiedzialnosci.objects.get(skrot='aut.')
            ).distinct(),
            punkty_kbn__gt=0)

    elif key == "2_2":
        return base_query.filter(
            charakter_formalny=Charakter_Formalny.objects.get(skrot="KSP"),
            punkty_kbn__gt=0)

    elif key == "2_3":
        return base_query.filter(
            charakter_formalny=Charakter_Formalny.objects.get(skrot="ROZ"),
            jezyk__in=jezyki_obce(),
            original__in_raw=Autorzy.objects.filter(
                jednostka_id=jednostka.pk,
                typ_odpowiedzialnosci_id=Typ_Odpowiedzialnosci.objects.get(skrot='aut.')
            ).distinct(),
            punkty_kbn__gt=0)

    elif key == "2_4":
        return base_query.filter(
            charakter_formalny=Charakter_Formalny.objects.get(skrot='ROZ'),
            jezyk=Jezyk.objects.get(skrot='pol.'),
            original__in_raw=Autorzy.objects.filter(
                jednostka_id=jednostka.pk,
                typ_odpowiedzialnosci_id=Typ_Odpowiedzialnosci.objects.get(skrot='aut.')
            ).distinct(),
            punkty_kbn__gt=0)

    elif key == "2_5":
        return base_query.filter(
            charakter_formalny=Charakter_Formalny.objects.get(skrot="KSZ"),
            jezyk__in=jezyki_obce(),
            punkty_kbn__gt=0,
            original__in_raw=Autorzy.objects.filter(
                jednostka_id=jednostka.pk,
                typ_odpowiedzialnosci_id=Typ_Odpowiedzialnosci.objects.get(skrot='red.')
            ).distinct()
        )

    elif key == "2_6":
        return base_query.filter(
            charakter_formalny=Charakter_Formalny.objects.get(skrot="KSP"),
            jezyk=Jezyk.objects.get(skrot='pol.'),
            original__in_raw=Autorzy.objects.filter(
                jednostka_id=jednostka.pk,
                typ_odpowiedzialnosci_id=Typ_Odpowiedzialnosci.objects.get(skrot='red.')
            ).distinct(),
            punkty_kbn__gt=0)


def get_base_query(jednostka, rok_min, rok_max):
    base = Rekord.objects.prace_jednostki(jednostka)
    if rok_min == rok_max:
        return base.filter(rok=rok_min)

    assert(rok_min < rok_max)
    return base.filter(rok__gte=rok_min, rok__lte=rok_max)

class RaportJednostek2012(DetailView):
    model = Jednostka
    template_name = "raporty/raport_jednostek_2012/index.html"

    def get_context_data(self, **kwargs):
        rok_min = self.kwargs['rok_min']
        rok_max = self.kwargs.get('rok_max', None)
        if rok_max is None:
            rok_max = rok_min

        base_query = get_base_query(
            jednostka=self.object,
            rok_min=rok_min,
            rok_max=rok_max)

        kw = dict(rok_min=rok_min, rok_max=rok_max)

        for key, klass in WSZYSTKIE_TABELE.items():
            kw['tabela_%s' % key] = klass(
                raport_jednostek_tabela(key, base_query, self.object))

        for tabela in [tabela for key, tabela in kw.items() if
                       key.startswith('tabela_')]:
            RequestConfig(self.request).configure(tabela)

        return DetailView.get_context_data(self, **kw)

