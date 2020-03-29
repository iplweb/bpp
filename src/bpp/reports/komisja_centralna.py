# -*- encoding: utf-8 -*-
import warnings
from decimal import Decimal
import os
import shutil
import tempfile
import sys

from celeryui.registry import ReportAdapter
from django.contrib.contenttypes.models import ContentType
from django.core.files import File
from django.db.models import Q, Sum
from django.template.loader import render_to_string
from django.utils import safestring
from django_tables2 import Column, A, Table

from bpp.models import (
    Autor,
    Typ_KBN,
    Rekord,
    Charakter_Formalny,
    Zasieg_Zrodla,
    Redakcja_Zrodla,
)

# from bpp.models.cache import cache_znajdz_autora_i_typ
from bpp.models.praca_habilitacyjna import Publikacja_Habilitacyjna
from bpp.models.system import Typ_Odpowiedzialnosci, Jezyk
from bpp.reports import addToRegistry
from bpp.util import Getter
from bpp.views.raporty.raport_aut_jed_common import (
    SumyImpactKbnMixin,
    sumpk_kc,
    sumif_kc,
)


class TabelaRaportuKomisjiCentralnejMixin(Table):
    lp = Column("Lp.", A("id"), empty_values=(), orderable=False)

    def __init__(self, *args, **kw):
        super(TabelaRaportuKomisjiCentralnejMixin, self).__init__(*args, **kw)
        self.counter = 0

    def render_lp(self, record):
        self.counter += 1
        return "%d." % self.counter


class TabelkaZImpactem(TabelaRaportuKomisjiCentralnejMixin, SumyImpactKbnMixin, Table):
    class Meta:
        attrs = {"class": "z_ramka"}
        template_name = "raporty/raport_komisji_centralnej/tabela_ia.html"
        per_page = sys.maxsize
        empty_text = "Brak takich rekordów."
        sequence = (
            "lp",
            "rok",
            "opis_bibliograficzny_cache",
            "impact_factor",
            "punkty_kbn",
        )

    rok = Column("Rok", orderable=False)
    opis_bibliograficzny_cache = Column(
        "Opis", orderable=False, attrs={"td": {"width": "70%"}}
    )

    def render_opis_bibliograficzny_cache(self, record):
        return safestring.mark_safe(record.opis_bibliograficzny_cache)


class TabelkaBezImpactu(TabelkaZImpactem):
    class Meta:
        template_name = "raporty/raport_komisji_centralnej/tabela_ib.html"
        sequence = ("lp", "rok", "opis_bibliograficzny_cache", "punkty_kbn")
        exclude = ["impact_factor"]
        attrs = {"class": "z_ramka"}


class Tabelka9Mixin(Table):
    impact_factor = Column(
        "IF", footer=sumif_kc, attrs={"td": {"align": "right"}}, orderable=False,
    )
    punkty_kbn = Column(
        "PK (MNiSzW)",
        footer=sumpk_kc,
        attrs={"td": {"align": "right"}},
        orderable=False,
    )

    def render_impact_factor(self, record):
        return record.kc_impact_factor or record.impact_factor

    def render_punkty_kbn(self, record):
        return record.kc_punkty_kbn or record.punkty_kbn


class TabelkaNr9A(Tabelka9Mixin, TabelkaZImpactem, Table):
    class Meta:
        template_name = "raporty/raport_komisji_centralnej/tabela_ia.html"
        attrs = {"class": "z_ramka"}
        sequence = (
            "lp",
            "rok",
            "opis_bibliograficzny_cache",
            "impact_factor",
            "punkty_kbn",
        )

        pass


class TabelkaNr9B(Tabelka9Mixin, TabelkaBezImpactu, Table):
    class Meta:
        template_name = "raporty/raport_komisji_centralnej/tabela_ib.html"
        attrs = {"class": "z_ramka"}
        sequence = (
            "lp",
            "rok",
            "opis_bibliograficzny_cache",
            "punkty_kbn",
        )
        exclude = [
            "impact_factor",
        ]

        pass


class RokHabilitacjiNiePodany(Exception):
    pass


def get_queries(autor, przed_habilitacja=True, rok_habilitacji=None):
    base_query = Rekord.objects.prace_autora(autor)

    if przed_habilitacja:
        if rok_habilitacji is not None:
            base_query = base_query.filter(rok__lte=rok_habilitacji)
    else:
        if rok_habilitacji is None:
            # Jeżeli chcesz raport PO habilitacji, ale autor NIE MA habilitacji,
            # to podnieś wyjątek:
            raise RokHabilitacjiNiePodany

        base_query = base_query.filter(rok__gt=rok_habilitacji)

    typ_kbn = Getter(Typ_KBN)
    typ_odpowiedzialnosci = Getter(Typ_Odpowiedzialnosci)
    charakter = Getter(Charakter_Formalny)
    zasieg = Getter(Zasieg_Zrodla, "nazwa")
    jezyk = Getter(Jezyk)

    ac = charakter.AC

    order_if = ("rok", "-impact_factor", "zrodlo")
    order_if_kc = ("rok", "-kc_impact_factor", "-impact_factor", "zrodlo")
    order_kbn = ("rok", "-punkty_kbn", "zrodlo")

    kw1 = dict(typ_kbn=typ_kbn.PO, charakter_formalny=ac)
    kw2 = dict(typ_kbn=typ_kbn.CR, charakter_formalny=ac)
    kw3 = dict(typ_kbn=typ_kbn.PP, charakter_formalny=ac)

    kw9 = dict(charakter_formalny=charakter.Supl)
    kw10 = dict(charakter_formalny=charakter.L)
    kw11 = dict(typ_kbn=typ_kbn.PW)

    impact = dict(impact_factor__gt=0)
    no_impact = dict(impact_factor=0)

    pkt_5_charaktery = []
    for skrot in [
        "BR",
        "FRG",
        "IN",
        "KOM",
        "PAT",
        "PZ",
        "SKR",
        "TŁ",
        "DE",
        "PRZ",
        "ZRZ",
        "R",
    ]:
        try:
            pkt_5_charaktery.append(Charakter_Formalny.objects.get(skrot__upper=skrot))
        except Charakter_Formalny.DoesNotExist:
            warnings.warn(
                "Brak charakteru formalnego %s dla punktu 5 raportu dla komisji centralnej"
                % skrot
            )
        # charakter.BR, charakter.frg, charakter.IN, charakter.KOM,
        # charakter.PAT, charakter.PZ, charakter.SKR, charakter['TŁ'],
        # charakter.DE, charakter.PRZ, charakter.ZRZ, charakter.R

    praca_habilitacyjna_content_type = ContentType.objects.get(
        app_label="bpp", model="praca_habilitacyjna"
    ).pk

    publikacje_habilitacyjne = Q(
        id__in=[
            (praca_habilitacyjna_content_type, pk.pk)
            for pk in Publikacja_Habilitacyjna.objects.filter().distinct().only("id")
        ]
    )

    try:
        jezyk_angielski = jezyk["ang."]
    except Jezyk.DoesNotExist:
        jezyk_angielski = jezyk["ENG"]

    ret = {
        "1a": base_query.filter(**dict(impact, **kw1)).order_by(*order_if),
        "1b": base_query.filter(**dict(no_impact, **kw1)).order_by(*order_kbn),
        "2a": base_query.filter(**dict(impact, **kw2)).order_by(*order_if),
        "2b": base_query.filter(**dict(no_impact, **kw2)).order_by(*order_kbn),
        "3a": base_query.filter(**dict(impact, **kw3)).order_by(*order_if),
        "3b": base_query.filter(**dict(no_impact, **kw3)).order_by(*order_kbn),
        "4c1": Rekord.objects.prace_autor_i_typ(autor, "aut.")
        .filter(
            charakter_formalny__in=[charakter.KSZ, charakter.H], jezyk=jezyk_angielski
        )
        .exclude(publikacje_habilitacyjne),
        "4c2": Rekord.objects.prace_autor_i_typ(autor, "aut.")
        .filter(charakter_formalny__in=[charakter.KSZ, charakter.KSP, charakter.H])
        .exclude(jezyk=jezyk_angielski)
        .exclude(publikacje_habilitacyjne),
        "5": base_query.filter(
            Q(charakter_formalny__in=pkt_5_charaktery)
            | Q(typ_kbn=typ_kbn["000"], charakter_formalny=charakter.AC)
            | Q(typ_kbn=typ_kbn.PNP)
            |
            # Habilitacja-składak
            publikacje_habilitacyjne,
        ).exclude(charakter_formalny__in=[charakter.PSZ, charakter.ZSZ]),
        "6a": Redakcja_Zrodla.objects.filter(
            redaktor=autor, zrodlo__zasieg=zasieg["krajowy"]
        )
        .values_list("zrodlo_id")
        .distinct(),
        "6b": Redakcja_Zrodla.objects.filter(
            redaktor=autor, zrodlo__zasieg=zasieg["międzynarodowy"]
        )
        .values_list("zrodlo_id")
        .distinct(),
        "7a": Rekord.objects.prace_autor_i_typ(autor, "red.").filter(
            jezyk=jezyk_angielski, charakter_formalny=charakter.KSZ
        ),
        "7b": Rekord.objects.prace_autor_i_typ(autor, "red.")
        .filter(charakter_formalny__in=[charakter.KSP, charakter.KSZ])
        .exclude(jezyk=jezyk_angielski),
        "8a": base_query.filter(charakter_formalny=charakter.ZSZ),
        "8b": base_query.filter(charakter_formalny=charakter.PSZ),
        "9a": base_query.filter(
            Q(Q(impact_factor__gt=0) | Q(kc_impact_factor__gt=0)), **kw9
        ).order_by(*order_if_kc),
        "9b": base_query.filter(
            Q(Q(impact_factor=0) & Q(Q(kc_impact_factor=0) | Q(kc_impact_factor=None))),
            **kw9
        ).order_by(*order_kbn),
        "10a": base_query.filter(**dict(impact, **kw10)).order_by(*order_if),
        "10b": base_query.filter(**dict(no_impact, **kw10)).order_by(*order_if),
        "11a": base_query.filter(**dict(impact, **kw11)).order_by(*order_if),
        "11b": base_query.filter(**dict(no_impact, **kw11)).order_by(*order_if),
        "IIIpat": base_query.filter(charakter_formalny=charakter.PAT),
    }
    return ret


class RaportKomisjiCentralnej:
    def __init__(self, autor, przed_habilitacja=True, rok_habilitacji=None):
        """

        :ptype autor: bpp.models.Autor
        :param przed_habilitacja: domyślnie wygeneruj raport dla autora przed
        habilitacją; jeżeli ten parametr jest False, zostaną wygenerowane dane
        dla autora PO habilitacji.
        """
        queries = get_queries(autor, przed_habilitacja, rok_habilitacji)

        self.dct = {}

        if rok_habilitacji is None:
            self.dct["rodzaj_dorobku"] = ""
            self.dct["stopien"] = "stopnia naukowego doktora habilitowanego"
        else:
            self.dct["stopien"] = "tytułu profesora"
            if przed_habilitacja:
                self.dct["rodzaj_dorobku"] = "Dorobek przedhabilitacyjny"
            else:
                self.dct["rodzaj_dorobku"] = "Dorobek pohabilitacyjny"

        impact_od_1_do_3 = 0
        kbn_od_1_do_3 = 0

        for key in ["1a", "1b", "2a", "2b", "3a", "3b"]:
            result = queries[key].aggregate(Sum("impact_factor"), Sum("punkty_kbn"))
            impact_od_1_do_3 += result["impact_factor__sum"] or 0
            kbn_od_1_do_3 += result["punkty_kbn__sum"] or 0

        liczba_streszczen_mnar = queries["8a"].count()
        liczba_streszczen_kraj = queries["8b"].count()
        liczba_streszczen = liczba_streszczen_kraj + liczba_streszczen_mnar

        def zsumuj(indeksy_zapytan):
            return sum([queries[x].count() for x in indeksy_zapytan])

        liczba_prac_I = zsumuj(["1a", "1b"])
        liczba_prac_II = zsumuj(["2a", "2b"])
        liczba_prac_III = zsumuj(["3a", "3b"])
        liczba_prac_IX = zsumuj(["9a", "9b"])

        liczba_prac_IVc1 = queries["4c1"].count()
        liczba_prac_IVc2 = queries["4c2"].count()

        self.dct.update(
            {
                "autor": autor,
                "extra": "TODO: extra",
                "liczba_prac_I": liczba_prac_I,
                "liczba_prac_II": liczba_prac_II,
                "liczba_prac_III": liczba_prac_III,
                "liczba_prac_IX": liczba_prac_IX,
                "tabela_1a": TabelkaZImpactem(queries["1a"]),
                "tabela_1b": TabelkaBezImpactu(queries["1b"]),
                "tabela_2a": TabelkaZImpactem(queries["2a"]),
                "tabela_2b": TabelkaBezImpactu(queries["2b"]),
                "tabela_3a": TabelkaZImpactem(queries["3a"]),
                "tabela_3b": TabelkaBezImpactu(queries["3b"]),
                "impact_od_1_do_3": impact_od_1_do_3,
                "kbn_od_1_do_3": kbn_od_1_do_3,
                "liczba_prac_IVc1": liczba_prac_IVc1,
                "liczba_prac_IVc2": liczba_prac_IVc2,
                "liczba_prac_IVc": liczba_prac_IVc2 + liczba_prac_IVc1,
                "liczba_prac_5": queries["5"].count(),
                "liczba_redaktor_mnar": queries["6a"].count(),
                "liczba_redaktor_kraj": queries["6b"].count(),
                "liczba_redaktor_wieloautorskich_ang": queries["7a"].count(),
                "liczba_redaktor_wieloautorskich_pol": queries["7b"].count(),
                "liczba_streszczen_kraj": liczba_streszczen_kraj,
                "liczba_streszczen_mnar": liczba_streszczen_mnar,
                "liczba_streszczen": liczba_streszczen,
                "tabela_9a": TabelkaNr9A(queries["9a"]),
                "tabela_9b": TabelkaNr9B(queries["9b"]),
                "tabela_10a": TabelkaZImpactem(queries["10a"]),
                "tabela_10b": TabelkaBezImpactu(queries["10b"]),
                "suma_10": queries["10a"].count() + queries["10b"].count(),
                "tabela_11a": TabelkaZImpactem(queries["11a"]),
                "tabela_11b": TabelkaBezImpactu(queries["11b"]),
                "suma_11": queries["11a"].count() + queries["11b"].count(),
                "IIIpat": queries["IIIpat"],
            }
        )

        self.rendered = False

    def make_prace(self):

        try:
            return render_to_string(
                "raporty/raport_komisji_centralnej/raport_bazowy.html", context=self.dct
            )
        finally:
            self.rendered = True

    def policz_sumy(self):
        if not self.rendered:
            # Wyrenderuj, żeby tabelki zsumowały wartości i żeby te wartości
            #  zostały zapisane na obiektach:
            self.make_prace()

        def sum_dict(*prefixes):
            count = 0
            impact_factor = Decimal("0.00")
            punkty_kbn = Decimal("0.00")

            for prefix in prefixes:
                tabela = self.dct["tabela_%s" % prefix]
                count += tabela.counter
                if hasattr(tabela, "sum_impact"):
                    impact_factor += tabela.sum_impact
                elif "impact_factor" in tabela.columns:
                    impact_factor += tabela.columns["impact_factor"].footer

                if hasattr(tabela, "sum_punkty_kbn"):
                    punkty_kbn += tabela.sum_punkty_kbn
                elif "punkty_kbn" in tabela.columns:
                    punkty_kbn += tabela.columns["punkty_kbn"].footer

            return dict(count=count, punkty_kbn=punkty_kbn, impact_factor=impact_factor)

        dct = {
            "suma_1": sum_dict("1a", "1b"),
            "suma_2": sum_dict("2a", "2b"),
            "suma_3": sum_dict("3a", "3b"),
            "suma_9": sum_dict("9a", "9b"),
            "suma_10": sum_dict("10a", "10b"),
            "suma_11": sum_dict("11a", "11b"),
            #'suma_4': sum_dict('4a', '4b'),
            "suma_5": dict(count=self.dct["liczba_prac_5"]),
            "suma_8": dict(count=self.dct["liczba_streszczen"]),
            "stopien": self.dct["stopien"],
            "rodzaj_dorobku": self.dct["rodzaj_dorobku"],
            "autor": self.dct["autor"],
        }

        return dct

    def punktacja_sumaryczna(self, partial=False):
        dct = self.policz_sumy()

        template_name = "raporty/raport_komisji_centralnej/" "punktacja_pojedyncza.html"
        if partial:
            template_name = "raporty/raport_komisji_centralnej/punktacja.html"

        return render_to_string(template_name, dct)


def make_report_zipfile(autor_id, rok_habilitacji):
    katalog = tempfile.mkdtemp("-bpp-kc-raport")
    current_dir = os.getcwd()

    zipname = None
    ret_path = None

    try:
        autor = Autor.objects.get(pk=autor_id)

        os.chdir(katalog)
        subdir = autor.slug + " - raport Komisji Centralnej"
        os.makedirs(subdir)
        os.chdir(subdir)

        base_fn = autor.slug
        filenames = []

        def save_encoded(fn, data):
            f = open(fn, "wb")
            f.write(data.encode("utf-8"))
            f.close()

        def fn(base, n, postfix):
            return "%s-%s-%s.html" % (base, n, postfix)

        if rok_habilitacji is not None:
            for postfix, arg in [("przed", True), ("po", False)]:
                raport = RaportKomisjiCentralnej(autor, arg, rok_habilitacji)

                save_encoded(fn(base_fn, "prace", postfix), raport.make_prace())

                # Zapisz "tymczasowy" pliki z punktacją, który później
                # zostaną połączony z drugim plikiem we wspólny raport:
                save_encoded(
                    fn(base_fn, "punktacja", postfix),
                    raport.punktacja_sumaryczna(partial=True),
                )

            dct = {"autor": raport.dct["autor"], "stopien": raport.dct["stopien"]}
            for postfix in ["przed", "po"]:
                dct[postfix] = open(fn(base_fn, "punktacja", postfix), "rb").read()

            data = render_to_string(
                "raporty/raport_komisji_centralnej/punktacja_podwojna.html", dct
            )

            f = open(fn(base_fn, "punktacja", "sumaryczna"), "wb")
            f.write(data.encode("utf-8"))
            f.close()

        else:
            raport = RaportKomisjiCentralnej(autor, True)
            for fun, n in [
                ("make_prace", "prace"),
                ("punktacja_sumaryczna", "punktacja"),
            ]:
                fn = "%s-%s.html" % (base_fn, n)
                data = getattr(raport, fun)()
                save_encoded(fn, data)

        zipname = "%s.zip" % subdir

        os.chdir("..")
        os.system('zip --quiet -r "%s" "%s" ' % (zipname, subdir))
        shutil.rmtree(subdir)

        return os.path.abspath(zipname)

    finally:
        os.chdir(current_dir)
        pass


class Raport_Dla_Komisji_Centralnej(ReportAdapter):
    slug = "raport-dla-komisji-centralnej"

    def _get_title(self):
        try:
            a = str(Autor.objects.get(pk=self.original.arguments["autor"]))
        except Autor.DoesNotExist:
            a = "(autor usunięty)"
        return "Raport dla Komisji Centralnej - %s" % a

    title = property(_get_title)

    def perform(self):
        try:
            rok_habilitacji = int(self.original.arguments["rok_habilitacji"])
        except (TypeError, ValueError):
            rok_habilitacji = None

        zipname = make_report_zipfile(
            autor_id=self.original.arguments["autor"], rok_habilitacji=rok_habilitacji
        )
        from django.core.files import File as FileWrapper

        self.original.file.save(
            os.path.basename(zipname),
            File(file=FileWrapper(open(zipname, "rb"), zipname)),
        )
        os.unlink(zipname)


addToRegistry(Raport_Dla_Komisji_Centralnej)
