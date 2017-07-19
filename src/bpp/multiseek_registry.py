# -*- encoding: utf-8 -*-
from django.contrib.postgres.search import SearchQuery
from django.utils.itercompat import is_iterable

from bpp.models.struktura import Wydzial
import six

NULL_VALUE = "(brak wpisanej wartości)"

from django.db.models import Q
from django.db.models.expressions import F
from multiseek import logic
from multiseek.logic import DecimalQueryObject, BooleanQueryObject
from multiseek.logic import StringQueryObject, QueryObject, EQUALITY_OPS_ALL, \
    UnknownOperation, DIFFERENT_ALL, AUTOCOMPLETE, EQUALITY_OPS_NONE, \
    EQUALITY_OPS_FEMALE, VALUE_LIST, EQUALITY_OPS_MALE, create_registry, IntegerQueryObject, ValueListQueryObject, \
    EQUAL, DIFFERENT, \
    AutocompleteQueryObject, Ordering, ReportType, RangeQueryObject, \
    DateQueryObject

from bpp.models import Typ_Odpowiedzialnosci, Jezyk, Autor, Jednostka, \
    Charakter_Formalny, Zrodlo
from bpp.models.cache import Autorzy, Rekord

from bpp.models.system import Typ_KBN


#
# class StringQueryObject(OrigStringQueryObject):
#     def value_for_description(self, value):
#         if not value:
#             return
#         return OrigStringQueryObject.value_for_description(self, value)


class TytulPracyQueryObject(StringQueryObject):
    label = 'Tytuł pracy'
    field_name = "tytul_oryginalny"

    def real_query(self, value, operation):
        ret = super(StringQueryObject, self).real_query(
            value, operation, validate_operation=False)

        if ret is not None:
            return ret

        elif operation in [logic.CONTAINS, logic.NOT_CONTAINS]:

            if not value:
                return Q(pk=F('pk'))

            value = [x.strip() for x in value.split(" ") if x.strip()]

            query = None
            for elem in value:
                if query is None:
                    query = SearchQuery(elem, config="bpp_nazwy_wlasne")
                else:
                    query &= SearchQuery(elem, config="bpp_nazwy_wlasne")

            if operation == logic.NOT_CONTAINS:
                query = ~query

            ret = Q(search_index=query)

        elif operation in [logic.STARTS_WITH, logic.NOT_STARTS_WITH]:
            ret = Q(**{self.field_name + "__istartswith": value})

            if operation in [logic.NOT_STARTS_WITH]:
                ret = ~ret
        else:
            raise UnknownOperation(operation)

        return ret


class AdnotacjeQueryObject(StringQueryObject):
    label = 'Adnotacje'
    field_name = 'adnotacje'
    public = False


class InformacjeQueryObject(StringQueryObject):
    label = 'Informacje'
    field_name = 'informacje'


class SzczegolyQueryObject(StringQueryObject):
    label = 'Szczegóły'
    field_name = 'szczegoly'


class UwagiQueryObject(StringQueryObject):
    label = 'Uwagi'
    field_name = 'uwagi'


class SlowaKluczoweQueryObject(StringQueryObject):
    label = 'Słowa kluczowe'
    field_name = 'slowa_kluczowe'


class DataUtworzeniaQueryObject(DateQueryObject):
    label = 'Data utworzenia'
    field_name = 'utworzono'
    public = False

    def value_for_description(self, value):
        value = self.value_from_web(value)
        if value is None:
            return NULL_VALUE
        if is_iterable(value):
            return "od %s do %s" % (value[0], value[1])
        return str(value)


class ForeignKeyDescribeMixin:
    def value_for_description(self, value):
        if value is None:
            return NULL_VALUE

        return self.model.objects.get(pk=int(value))


class NazwiskoIImieQueryObject(ForeignKeyDescribeMixin, AutocompleteQueryObject):
    label = 'Nazwisko i imię'
    type = AUTOCOMPLETE
    ops = EQUALITY_OPS_NONE
    model = Autor
    search_fields = ['nazwisko', 'imiona']
    field_name = 'autor'

    def real_query(self, value, operation):

        if operation in EQUALITY_OPS_ALL:
            ret = Q(original__in_raw=Autorzy.objects.filter(autor=value))

        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret
        return ret

    def get_autocomplete_query(self, data):
        if six.PY3:
            if type(data) == bytes:
                data = data.decode("utf-8")
        return Autor.objects.fulltext_filter(data)


class JednostkaQueryObject(ForeignKeyDescribeMixin, AutocompleteQueryObject):
    label = 'Jednostka'
    type = AUTOCOMPLETE
    ops = EQUALITY_OPS_FEMALE
    model = Jednostka
    search_fields = ['nazwa']
    field_name = 'jednostka'

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(original__in_raw=Autorzy.objects.filter(jednostka=value))

        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret
        return ret

    def get_autocomplete_query(self, data):
        if six.PY3:
            if type(data) == bytes:
                data = data.decode("utf-8")
        return Jednostka.objects.fulltext_filter(data)


class WydzialQueryObject(ForeignKeyDescribeMixin, AutocompleteQueryObject):
    label = 'Wydział'
    type = AUTOCOMPLETE
    ops = EQUALITY_OPS_MALE
    model = Wydzial
    search_fields = ['nazwa']
    field_name = 'wydzial'

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(original__in_raw=Autorzy.objects.filter(jednostka__wydzial=value))

        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret
        return ret

    def get_autocomplete_query(self, data):
        return Wydzial.objects.filter(nazwa__icontains=data)


class Typ_OdpowiedzialnosciQueryObject(QueryObject):
    label = 'Typ odpowiedzialności'
    type = VALUE_LIST
    values = Typ_Odpowiedzialnosci.objects.all()
    ops = EQUALITY_OPS_MALE
    field_name = 'typ_odpowiedzialnosci'

    def value_from_web(self, value):
        return Typ_Odpowiedzialnosci.objects.get(nazwa=value)

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(original__in_raw=Autorzy.objects.filter(typ_odpowiedzialnosci=value))
        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret
        return ret


class ZakresLatQueryObject(RangeQueryObject):
    label = 'Zakres lat'
    field_name = 'rok'


class JezykQueryObject(QueryObject):
    label = 'Język'
    type = VALUE_LIST
    ops = EQUALITY_OPS_MALE
    values = Jezyk.objects.all()
    field_name = "jezyk"

    def value_from_web(self, value):
        return Jezyk.objects.get(nazwa=value)


class RokQueryObject(IntegerQueryObject):
    label = 'Rok'
    field_name = 'rok'


class ImpactQueryObject(DecimalQueryObject):
    label = 'Impact factor'
    field_name = 'impact_factor'


class KCImpactQueryObject(ImpactQueryObject):
    field_name = 'kc_impact_factor'
    label = "KC: Impact factor"
    public = False


class PunktacjaWewnetrznaQueryObject(DecimalQueryObject):
    label = "Punktacja wewnętrzna"
    field_name = "punktacja_wewnetrzna"


class KCPunktacjaWewnetrznaQueryObject(PunktacjaWewnetrznaQueryObject):
    field_name = 'kc_punktacja_wewnetrzna'
    label = "KC: Punktacja wewnętrzna"
    public = False


class PunktyKBNQueryObject(DecimalQueryObject):
    label = "Punkty PK"
    field_name = "punkty_kbn"


class KCPunktyKBNQueryObject(PunktyKBNQueryObject):
    label = "KC: Punkty PK"
    field_name = 'kc_punkty_kbn'
    public = False


class IndexCopernicusQueryObject(DecimalQueryObject):
    label = "Index Copernicus"
    field_name = "index_copernicus"


class LiczbaZnakowWydawniczychQueryObject(IntegerQueryObject):
    label = 'Liczba znaków wydawniczych'
    field_name = 'liczba_znakow_wydawniczych'


class TypRekorduObject(ValueListQueryObject):
    label = 'Typ rekordu'
    values = ['publikacje', 'streszczenia', 'inne']
    ops = [EQUAL, DIFFERENT]

    def value_from_web(self, value):
        if value not in self.values:
            return
        return value

    def real_query(self, value, operation):
        if value == 'publikacje':
            charaktery = Charakter_Formalny.objects.filter(publikacja=True)
        elif value == 'streszczenia':
            charaktery = Charakter_Formalny.objects.filter(streszczenie=True)
        elif value == 'inne':
            charaktery = Charakter_Formalny.objects.all().exclude(
                streszczenie=True).exclude(publikacja=True)

        q = Q(**{'charakter_formalny__in': charaktery})
        if operation == DIFFERENT:
            return ~q
        return q


class CharakterFormalnyQueryObject(ValueListQueryObject):
    field_name = 'charakter_formalny'
    values = Charakter_Formalny.objects.all()
    label = "Charakter formalny"

    def value_from_web(self, value):
        return Charakter_Formalny.objects.get(nazwa=value)


class TypKBNQueryObject(ValueListQueryObject):
    field_name = "typ_kbn"
    values = Typ_KBN.objects.all()
    label = "Typ KBN"

    def value_from_web(self, value):
        return Typ_KBN.objects.get(nazwa=value)


class ZrodloQueryObject(AutocompleteQueryObject):
    label = 'Źródło'
    ops = EQUALITY_OPS_NONE
    model = Zrodlo
    field_name = 'zrodlo'

    def get_autocomplete_query(self, data):
        return Zrodlo.objects.fulltext_filter(data)


class AfiliowanaQueryObject(BooleanQueryObject):
    field_name = "afiliowana"
    label = "Praca afiliowana"


class RecenzowanaQueryObject(BooleanQueryObject):
    field_name = "recenzowana"
    label = "Praca recenzowana"


registry = create_registry(
    Rekord,
    TytulPracyQueryObject(),
    NazwiskoIImieQueryObject(),
    JednostkaQueryObject(),
    WydzialQueryObject(),
    Typ_OdpowiedzialnosciQueryObject(),
    ZakresLatQueryObject(),
    JezykQueryObject(),
    RokQueryObject(),
    TypRekorduObject(),
    CharakterFormalnyQueryObject(),
    TypKBNQueryObject(),
    ZrodloQueryObject(),

    ImpactQueryObject(),
    PunktyKBNQueryObject(),
    IndexCopernicusQueryObject(),
    PunktacjaWewnetrznaQueryObject(),

    KCImpactQueryObject(),
    KCPunktyKBNQueryObject(),
    KCPunktacjaWewnetrznaQueryObject(),

    InformacjeQueryObject(),
    SzczegolyQueryObject(),
    UwagiQueryObject(),
    SlowaKluczoweQueryObject(),

    AdnotacjeQueryObject(),
    DataUtworzeniaQueryObject(),

    AfiliowanaQueryObject(),
    RecenzowanaQueryObject(),

    LiczbaZnakowWydawniczychQueryObject(),

    ordering=[
        Ordering("", "(nieistotne)"),
        Ordering("tytul_oryginalny", "tytuł oryginalny"),
        Ordering("rok", "rok"),
        Ordering("impact_factor", "impact factor"),
        Ordering("punkty_kbn", "punkty PK"),
        Ordering("charakter_formalny__nazwa", "charakter formalny"),
        Ordering("typ_kbn__nazwa", "typ KBN"),
        Ordering("zrodlo__nazwa", "źródło"),
    ],
    default_ordering=['-rok', '-impact_factor', '-punkty_kbn'],
    report_types=[
        ReportType("list", "lista"),
        ReportType("table", "tabela"),
        ReportType("pkt_wewn", "punktacja sumaryczna z punktacją wewnętrzna"),
        ReportType("pkt_wewn_bez",
                   "punktacja sumaryczna bez punktacji wewnętrznej"),
        ReportType("numer_list", "numerowana lista z uwagami", public=False)
    ])
