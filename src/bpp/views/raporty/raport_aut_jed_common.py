# -*- encoding: utf-8 -*-


"""Wspólne procedury dla raportu jednostek oraz autorów.
"""

import itertools
import sys
import urllib.request, urllib.parse, urllib.error
from decimal import Decimal

import bleach
from django.db.models.query_utils import Q

from bpp.models import Charakter_Formalny, Jezyk, Typ_Odpowiedzialnosci
from bpp.models.cache import Autorzy, Rekord
from bpp.models.system import Typ_KBN
from bpp.models.abstract import ILOSC_ZNAKOW_NA_ARKUSZ
from django.core.exceptions import ObjectDoesNotExist
from django.http.response import HttpResponse
from django.template import loader
from collections import OrderedDict as SortedDict
from django.utils.safestring import mark_safe
from django.views.generic.detail import DetailView
from django_tables2 import A, Column, Table


def sumif(table):
    return sum(x.impact_factor for x in table.data)


def sumpk(table):
    return sum(x.punkty_kbn for x in table.data)


def sumif_kc(table):
    return sum(x.kc_impact_factor or x.impact_factor for x in table.data)


def sumpk_kc(table):
    return sum(x.kc_punkty_kbn or x.punkty_kbn for x in table.data)


class SumyImpactKbnMixin(Table):
    impact_factor = Column(
        "IF", footer=sumif_kc, attrs={"td": {"align": "right"}}, orderable=False,
    )
    punkty_kbn = Column(
        "PK (MNiSzW) x",
        footer=sumpk_kc,
        attrs={"td": {"align": "right"}},
        orderable=False,
    )


class TypowaTabelaMixin(Table):
    lp = Column("Lp.", A("id"), empty_values=(), orderable=False)
    tytul_oryginalny = Column("Tytuł")
    jezyk = Column("Język", A("jezyk.skrot"), orderable=False)
    autorzy = Column(
        "Autor (autorzy)",
        A("opis_bibliograficzny_zapisani_autorzy_cache"),
        orderable=False,
    )

    def __init__(self, *args, **kw):
        super(TypowaTabelaMixin, self).__init__(*args, **kw)
        self.counter = 0

    def render_lp(self, record):
        self.counter += 1
        return "%d." % self.counter

    #
    # def render_autorzy(self, record):
    #     return record.opis_bibliograficzny_zapisani_autorzy_cache

    def render_tytul_oryginalny(self, record):
        return mark_safe(record.tytul_oryginalny)


class Tabela_Publikacji(TypowaTabelaMixin, SumyImpactKbnMixin, Table):
    class Meta:
        attrs = {"class": "paleblue"}
        template = "raporty/raport_jednostek_autorow_2012/publikacje.html"
        per_page = sys.maxsize
        empty_text = "Brak takich rekordów."
        sequence = (
            "lp",
            "zrodlo",
            "lp_art",
            "autorzy",
            "tytul_oryginalny",
            "rok",
            "szczegoly",
            "punkty_kbn",
        )

    span_rows = 7
    print_sum_impact = False

    zrodlo = Column("Czasopismo", A("zrodlo.nazwa"), orderable=False)
    lp_art = Column("Lp. art.", A("id"), empty_values=(), orderable=False)
    rok = Column("Rok, tom/nr", A("rok"), orderable=False)
    szczegoly = Column("Szczegóły", A("szczegoly"))

    def __init__(self, *args, **kwargs):
        super(Tabela_Publikacji, self).__init__(*args, **kwargs)
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
            new_zrodlo = ""

        if self.old_zrodlo != new_zrodlo:
            self.counter += 1
            self.zrodlo_counter = itertools.count(1)
            self.old_zrodlo = new_zrodlo
            self.nowe_zrodlo_w_wierszu = True
        else:
            self.nowe_zrodlo_w_wierszu = False

        if self.nowe_zrodlo_w_wierszu:
            return "%d." % self.counter
        return ""

    def render_zrodlo(self, record):
        if self.nowe_zrodlo_w_wierszu:
            return record.zrodlo.nazwa

        return ""

    def render_szczegoly(self, record):
        return record.szczegoly

    def render_rok(self, record):
        if str(record.rok) in record.informacje:
            return record.informacje
        return "%s, %s" % (record.rok, record.informacje)


class Tabela_Publikacji_Z_Impactem(Tabela_Publikacji):
    class Meta:
        attrs = {"class": "paleblue"}
        template = "raporty/raport_jednostek_autorow_2012/publikacje.html"
        per_page = sys.maxsize
        empty_text = "Brak takich rekordów."
        sequence = (
            "lp",
            "zrodlo",
            "lp_art",
            "autorzy",
            "tytul_oryginalny",
            "rok",
            "szczegoly",
            "impact_factor",
            "punkty_kbn",
        )

    span_rows = 7
    print_sum_impact = True


class Tabela_Konferencji_Miedzynarodowej(TypowaTabelaMixin, SumyImpactKbnMixin, Table):
    class Meta:
        attrs = {"class": "paleblue"}
        template = "raporty/raport_jednostek_autorow_2012/publikacje.html"
        per_page = sys.maxsize
        empty_text = "Brak takich rekordów."
        sequence = (
            "lp",
            "zrodlo",
            "lp_art",
            "autorzy",
            "tytul_oryginalny",
            "rok",
            "zakres",
            "punkty_kbn",
        )

    span_rows = 7
    print_sum_impact = False

    zrodlo = Column("Tytuł materiału konf.", A("informacje"), orderable=False)
    lp_art = Column("Lp. ref.", A("id"), empty_values=(), orderable=False)
    rok = Column("Rok")
    zakres = Column("Zakres stron ref.", A("szczegoly"), orderable=False)

    def __init__(self, *args, **kwargs):
        super(Tabela_Konferencji_Miedzynarodowej, self).__init__(*args, **kwargs)
        self.zrodlo_counter = itertools.count(1)
        self.output_zrodlo = False
        self.old_zrodlo = None

    def render_lp_art(self, record):
        ret = "%s.%s." % (self.counter, next(self.zrodlo_counter))
        return ret

    def render_lp(self, record):
        # record.zrodlo moze byc None
        try:
            new_zrodlo = record.informacje
        except ObjectDoesNotExist:
            new_zrodlo = ""

        if self.old_zrodlo != new_zrodlo:
            self.counter += 1
            self.zrodlo_counter = itertools.count(1)
            self.old_zrodlo = new_zrodlo
            self.nowe_zrodlo_w_wierszu = True
        else:
            self.nowe_zrodlo_w_wierszu = False

        if self.nowe_zrodlo_w_wierszu:
            return "%d." % self.counter
        return ""

    def render_zrodlo(self, record):
        if self.nowe_zrodlo_w_wierszu:
            return record.informacje.strip("W: ")

        return ""

    def render_zakres(self, record):
        buf = record.szczegoly
        # if record.uwagi:
        #     buf += u", " + record.uwagi
        #
        buf = buf.strip("WoS").strip()
        return buf


class Tabela_Monografii(TypowaTabelaMixin, SumyImpactKbnMixin, Table):
    class Meta:
        attrs = {"class": "paleblue"}
        template = "raporty/raport_jednostek_autorow_2012/monografie.html"
        per_page = sys.maxsize
        empty_text = "Brak takich rekordów."
        sequence = (
            "lp",
            "autorzy",
            "wydawca",
            "tytul_oryginalny",
            "jezyk",
            "rok",
            "szczegoly",
            "punkty_kbn",
        )

    szczegoly = Column("Szczegóły", A("szczegoly"))

    wydawca = Column("Wydawca", A("wydawnictwo"), orderable=False)
    rok = Column("Rok", orderable=False)

    def render_szczegoly(self, record):
        buf = record.szczegoly
        if record.uwagi:
            buf += ", " + record.uwagi
        return buf


class Tabela_Redakcji_Naukowej(TypowaTabelaMixin, SumyImpactKbnMixin, Table):
    class Meta:
        attrs = {"class": "paleblue"}
        template = "raporty/raport_jednostek_autorow_2012/monografie.html"
        per_page = sys.maxsize
        empty_text = "Brak takich rekordów."
        sequence = (
            "lp",
            "redaktorzy",
            "wydawca",
            "tytul_oryginalny",
            "jezyk",
            "rok",
            "szczegoly",
            "punkty_kbn",
        )

    szczegoly = Column("Szczegóły", A("szczegoly"))

    wydawca = Column("Wydawca", A("wydawnictwo"), orderable=False)
    rok = Column("Rok", orderable=False)

    redaktorzy = Column(
        "Redaktor (redaktorzy)",
        A("opis_bibliograficzny_autorzy_cache"),
        orderable=False,
    )

    def render_redaktorzy(self, record):
        klass = record.original.autorzy.through
        to = Typ_Odpowiedzialnosci.objects.get(skrot="red.")
        reds = klass.objects.filter(rekord=record.original, typ_odpowiedzialnosci=to)
        return ", ".join([x.zapisany_jako for x in reds])


def split_red(s, want, if_no_result=None):
    seps = [
        "Pod. red.",
        "Pod red.",
        "Red. nauk.",
        "red.",
        "Pod redakcją",
        "pod redakcją",
        "Red.",
        "Ed. by",
    ]

    for sep in seps:
        if s.find(sep) > 0:
            x = s.split(sep)
            if len(x) > want:
                return x[want]

    if if_no_result:
        return if_no_result

    return s


def get_tytul_monografii(record):
    orig = record.original

    if hasattr(orig, "wydawnictwo_nadrzedne"):
        wn = orig.wydawnictwo_nadrzedne
        if wn is not None:
            return wn.tytul_oryginalny

    return split_red(record.informacje, 0, if_no_result="").replace("W: ", "")


class Tabela_Rozdzialu_Monografii(TypowaTabelaMixin, SumyImpactKbnMixin, Table):
    class Meta:
        attrs = {"class": "paleblue"}
        template = "raporty/raport_jednostek_autorow_2012/rozdzialy_monografii.html"
        per_page = sys.maxsize
        empty_text = "Brak takich rekordów."
        sequence = (
            "lp",
            "tytul",
            "wydawca",
            "lp_rozdzialu",
            "autorzy",
            "tytul_rozdzialu",
            "jezyk",
            "rok",
            "szczegoly",
            # 'impact_factor',
            # redaktor monografii
            "punkty_kbn",
        )

    tytul = Column("Tytuł monografii", A("pk"))
    tytul_rozdzialu = Column("Tytuł rozdziału", A("tytul_oryginalny"))

    wydawca = Column("Wydawca", A("wydawnictwo"), orderable=False)
    # impact_factor  = Column("Redaktor monografii")
    rok = Column("Rok", orderable=False)
    szczegoly = Column("Szczegóły", A("szczegoly"))
    lp_rozdzialu = Column("Lp. rozdziału", A("szczegoly"))

    def __init__(self, *args, **kwargs):
        super(Tabela_Rozdzialu_Monografii, self).__init__(*args, **kwargs)

        self.counter = 0
        self.old_tm = None

    def render_lp(self, record):
        tm = get_tytul_monografii(record)

        if self.old_tm != tm:
            self.counter += 1
            self.tm_counter = itertools.count(1)
            self.old_tm = tm
            self.nowy_tytul_w_wierszu = True
        else:
            self.nowy_tytul_w_wierszu = False

        if self.nowy_tytul_w_wierszu:
            return "%d." % self.counter
        return ""

    def render_lp_rozdzialu(self, record):
        ret = "%s.%s." % (self.counter, next(self.tm_counter))
        return ret

    def render_tytul(self, record):
        if self.nowy_tytul_w_wierszu:
            return get_tytul_monografii(record)
        return ""

    def render_wydawca(self, record):
        if self.nowy_tytul_w_wierszu:
            return record.wydawnictwo
        return ""

    def render_tytul_rozdzialu(self, record):
        return record.tytul_oryginalny

    def render_szczegoly(self, record):
        buf = record.szczegoly
        if record.uwagi:
            buf += ", " + record.uwagi
        return buf

        # def render_impact_factor(self, record): # redaktor monografii
        #     orig = record.original
        #
        #     if hasattr(orig, 'wydawnictwo_nadrzedne'):
        #         wn = orig.wydawnictwo_nadrzedne
        #         if wn is not None:
        #             redaktorzy = Wydawnictwo_Zwarte_Autor.objects.filter(
        #                 rekord=wn,
        #                 typ_odpowiedzialnosci=Typ_Odpowiedzialnosci.objects.get(
        #                     skrot='red.'))
        #
        #             return u", ".join([unicode(red) for red in redaktorzy])
        #
        #     return split_red(record.informacje, 1, "").strip(" .")


def wiele(model, *args):
    return [model.objects.get(skrot=x) for x in args]


def charaktery(*args):
    return wiele(Charakter_Formalny, *args)


def jezyki(*args):
    return wiele(Jezyk, *args)


def jezyki_obce():
    return jezyki("ang.", "niem.", "fr.", "hiszp.", "ros.", "wł.")


WSZYSTKIE_TABELE = SortedDict(
    [
        ("1_1", Tabela_Publikacji_Z_Impactem),
        ("1_2", Tabela_Publikacji),
        ("1_3", Tabela_Publikacji),
        ("1_4", Tabela_Publikacji),
        ("1_5", Tabela_Konferencji_Miedzynarodowej),
        ("2_1", Tabela_Monografii),
        ("2_2", Tabela_Rozdzialu_Monografii),
        ("2_3", Tabela_Redakcji_Naukowej),
    ]
)


def get_extra_kw_for_jednostka(jednostka, typ_autora_skrot):
    return {
        "autorzy__jednostka_id": jednostka.pk,
        "autorzy__typ_odpowiedzialnosci__skrot": typ_autora_skrot,
    }


def get_extra_kw_for_autor(autor, typ_autora_skrot):
    return {
        "autorzy__autor_id": autor.pk,
        "autorzy__typ_odpowiedzialnosci__skrot": typ_autora_skrot,
    }


def raport_common_tabela(key, base_query, jednostka=None, autor=None):
    """Modyfikuje base_query według zadanego klucza.
    """
    """Modyfikuje queryset base_query według parametrów dla zadanego
    raportu (key)
    """

    assert not (jednostka != None and autor != None), "albo autor, albo jednostka"

    if key == "1_1":
        return (
            base_query.filter(impact_factor__gt=0, punktacja_wewnetrzna=0)
            .exclude(adnotacje__icontains="wos")
            .exclude(adnotacje__icontains="erih")
            .exclude(typ_kbn=Typ_KBN.objects.get(skrot="PW"))
            .order_by("zrodlo__nazwa")
        )

    elif key == "1_2":
        # (Charakter formalny= AC OR L OR Supl) AND IF=0 AND PK>0 AND NOT
        # [(Charakter formalny= AC OR L OR Supl) AND IF=0 PK>0 AND l. znaków> 20000]

        return (
            base_query.filter(
                charakter_formalny__skrot__in=["AC", "L", "Supl"],
                impact_factor=0,
                punkty_kbn__gt=0,
            )
            .exclude(adnotacje__icontains="wos")
            .exclude(adnotacje__icontains="erih")
            .exclude(typ_kbn=Typ_KBN.objects.get(skrot="PW"))
        )

    elif key == "1_3":
        return base_query.filter(adnotacje__icontains="erih", punkty_kbn__gt=0)

    elif key == "1_4":
        # 1.4 Recenzowana publikacja naukowa w języku innym niż polski w
        # zagranicznym czasopiśmie naukowym spoza list A,B,C, o objętości co
        # najmniej 0,5 arkusza

        # (Charakter formalny= AC OR L OR Supl) AND IF=0 AND PK>0 AND l. znaków> 20000

        return base_query.filter(
            liczba_znakow_wydawniczych__gte=ILOSC_ZNAKOW_NA_ARKUSZ / 2,
            charakter_formalny__skrot__in=["AC", "L", "Supl"],
            impact_factor=0,
            punkty_kbn__gt=0,
        ).exclude(jezyk=Jezyk.objects.get(skrot="pol."))

    elif key == "1_5":
        return base_query.filter(adnotacje__icontains="wos", punkty_kbn__gt=0)

    elif key == "2_1":
        extra_kw = {}
        # Jeżeli podana jest jednostka jako parametr, no to wówczas wyszukujemy
        # autorów tylko z tej jednostki o zadanym typie:
        if jednostka is not None:
            extra_kw = get_extra_kw_for_jednostka(jednostka, "aut.")
        if autor is not None:
            extra_kw = get_extra_kw_for_autor(autor, "aut.")
        return base_query.filter(
            charakter_formalny__in=[
                Charakter_Formalny.objects.get(skrot="KSZ"),
                Charakter_Formalny.objects.get(skrot="KSP"),
                Charakter_Formalny.objects.get(skrot="KS"),
            ],
            punkty_kbn__gt=0,
            **extra_kw
        )

    elif key == "2_2":
        extra_kw = {}
        # Jeżeli podana jest jednostka jako parametr, no to wówczas wyszukujemy
        # autorów tylko z tej jednostki o zadanym typie:
        if jednostka is not None:
            extra_kw = get_extra_kw_for_jednostka(jednostka, "aut.")
        if autor is not None:
            extra_kw = get_extra_kw_for_autor(autor, "aut.")
        return base_query.filter(
            charakter_formalny=Charakter_Formalny.objects.get(skrot="ROZ"),
            punkty_kbn__gt=0,
            **extra_kw
        ).order_by("informacje", "tytul_oryginalny")

    elif key == "2_3":
        extra_kw = {}
        # Jeżeli podana jest jednostka jako parametr, no to wówczas wyszukujemy
        # autorów tylko z tej jednostki o zadanym typie:
        if jednostka is not None:
            extra_kw = get_extra_kw_for_jednostka(jednostka, "red.")
        if autor is not None:
            extra_kw = get_extra_kw_for_autor(autor, "red.")
        return base_query.filter(
            charakter_formalny__in=[
                Charakter_Formalny.objects.get(skrot="KSZ"),
                Charakter_Formalny.objects.get(skrot="KSP"),
                Charakter_Formalny.objects.get(skrot="KS"),
            ],
            punkty_kbn__gt=0,
            **extra_kw
        )


def raport_jednostek_tabela(key, base_query, jednostka):
    return raport_common_tabela(key, base_query, jednostka=jednostka)


def raport_autorow_tabela(key, base_query, autor):
    return raport_common_tabela(key, base_query, autor=autor)


def _get_base_query(fun, param, rok_min, rok_max):
    base = fun(param)
    if rok_min == rok_max:
        return base.filter(rok=rok_min)

    assert rok_min < rok_max
    return base.filter(rok__gte=rok_min, rok__lte=rok_max)


def get_base_query_jednostka(jednostka, *args, **kw):
    return _get_base_query(Rekord.objects.prace_jednostki, jednostka, *args, **kw)


def get_base_query_autor(autor, *args, **kw):
    return _get_base_query(
        Rekord.objects.prace_autora_z_afiliowanych_jednostek, autor, *args, **kw
    )


MSW_ALLOWED_TAGS = [
    "abbr",
    "acronym",
    "b",
    "blockquote",
    "code",
    "em",
    "i",
    "li",
    "ol",
    "strong",
    "ul",
    "center",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "table",
    "tr",
    "td",
    "th",
    "div",
    "thead",
    "tbody",
    "body",
    "head",
    "meta",
    "html",
]

MSW_ALLOWED_ATTRIBUTES = {
    "a": ["href", "title"],
    "td": ["colspan", "rowspan", "align", "valign"],
    "abbr": ["title"],
    "acronym": ["title"],
    "meta": ["charset"],
}


class MSWordFromTemplateResponse(HttpResponse):
    def __init__(self, request, context, template_name, visible_name, *args, **kwargs):
        super(HttpResponse, self).__init__(*args, **kwargs)
        self["Content-type"] = "application/msword"
        self["Content-disposition"] = "attachment; filename=%s" % visible_name.encode(
            "utf-8"
        )  # urllib.quote(visible_name.encode("utf-8"))
        c = loader.render_to_string(template_name, context, request=request)
        c = bleach.clean(
            c, tags=MSW_ALLOWED_TAGS, attributes=MSW_ALLOWED_ATTRIBUTES, strip=True
        )
        c = c.replace("<table>", "<table border=1 cellspacing=0>")
        self.content = (
            '<html><head><meta charset="utf-8"></head><body>' + c + "</body></html>"
        )
        self["Content-length"] = len(self.content)


class Raport2012CommonView(DetailView):
    def get(self, request, *args, **kwargs):
        self.object = self.get_object()
        context = self.get_context_data(object=self.object)
        if context["output"] == "msw":
            zakres_lat = "%s" % context["rok_min"]
            if context["rok_min"] != context["rok_max"]:
                zakres_lat += "-%s" % context["rok_max"]
            nazwa_pliku = "raport-%s-%s.doc" % (
                self.get_short_object_name().replace(".", "").replace(" ", ""),
                zakres_lat,
            )
            return MSWordFromTemplateResponse(
                self.request,
                context,
                "raporty/raport_jednostek_autorow_2012/raport_common.html",
                nazwa_pliku,
            )
        return self.render_to_response(context)
