# -*- encoding: utf-8 -*-
from django.contrib.contenttypes.models import ContentType
from django.utils.itercompat import is_iterable

NULL_VALUE = u"(brak wpisanej wartości)"

from dateutil.parser import parse as parse_string_date
from django.db.models import Q
from django.utils.datastructures import SortedDict
from bpp import autocomplete_light_registry
from django.db.models.expressions import F
from djorm_pgfulltext.fields import TSConfig
from multiseek import logic
from multiseek.logic import DecimalQueryObject
from multiseek.logic import StringQueryObject, QueryObject, EQUALITY_OPS_ALL, \
    UnknownOperation, DIFFERENT_ALL, AUTOCOMPLETE, EQUALITY_OPS_NONE, \
    EQUALITY_OPS_FEMALE, VALUE_LIST, EQUALITY_OPS_MALE, RANGE, RANGE_OPS, \
    create_registry, IntegerQueryObject, ValueListQueryObject, EQUAL, DIFFERENT, \
    AutocompleteQueryObject, Ordering, ReportType, RangeQueryObject, \
    DateQueryObject

from bpp.models import Typ_Odpowiedzialnosci, Jezyk, Autor, Jednostka, \
    Charakter_Formalny, Zrodlo
from bpp.models.cache import Autorzy, Rekord

from bpp.models.system import Typ_KBN


class TytulPracyQueryObject(StringQueryObject):
    label = u'Tytuł pracy'
    field_name = "tytul_oryginalny"

    def real_query(self, value, operation):
        ret = super(StringQueryObject, self).real_query(
            value, operation, validate_operation=False)

        if ret is not None:
            return ret

        elif operation in [logic.CONTAINS, logic.NOT_CONTAINS]:

            value = [x.strip() for x in value.split(" ") if x.strip()]

            if not value:
                return Q(pk=F('pk'))

            params = [TSConfig('bpp_nazwy_wlasne')]
            params.extend(value)

            if operation == logic.CONTAINS:
                ret = Q(search_index__ft_startswith=params)
            else:
                ret = Q(search_index__ft_not_startswith=params)

        elif operation in [logic.STARTS_WITH, logic.NOT_STARTS_WITH]:
            ret = Q(**{self.field_name + "__istartswith": value})

            if operation in [logic.NOT_STARTS_WITH]:
                ret = ~ret
        else:
            raise UnknownOperation(operation)

        return ret


class AdnotacjeQueryObject(StringQueryObject):
    label = u'Adnotacje'
    field_name = 'adnotacje'
    public = False


class DataUtworzeniaQueryObject(DateQueryObject):
    label = u'Data utworzenia'
    field_name = 'utworzono'
    public = False

    def value_for_description(self, value):
        value = self.value_from_web(value)
        if value is None:
            return NULL_VALUE
        if is_iterable(value):
            return u"od %s do %s" % (value[0], value[1])
        return unicode(value)


class ForeignKeyDescribeMixin:

    def value_for_description(self, value):
        if value is None:
            return NULL_VALUE

        return self.model.objects.get(pk=int(value))

class NazwiskoIImieQueryObject(ForeignKeyDescribeMixin, AutocompleteQueryObject):
    label = u'Nazwisko i imię'
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
        return Autor.objects.fulltext_filter(data)


class JednostkaQueryObject(ForeignKeyDescribeMixin, AutocompleteQueryObject):
    label = u'Jednostka dowolnego autora'
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
        return Jednostka.objects.fulltext_filter(data)



class ZakresLatQueryObject(RangeQueryObject):
    label = u'Zakres lat'
    field_name = 'rok'


class JezykQueryObject(QueryObject):
    label = u'Język'
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
    label = u"Punktacja wewnętrzna"
    field_name = "punktacja_wewnetrzna"


class KCPunktacjaWewnetrznaQueryObject(PunktacjaWewnetrznaQueryObject):
    field_name = 'kc_punktacja_wewnetrzna'
    label = u"KC: Punktacja wewnętrzna"
    public = False


class PunktyKBNQueryObject(DecimalQueryObject):
    label = "Punkty KBN"
    field_name = "punkty_kbn"


class KCPunktyKBNQueryObject(PunktyKBNQueryObject):
    label = u"KC: Punkty KBN"
    field_name = 'kc_punkty_kbn'
    public = False


class IndexCopernicusQueryObject(DecimalQueryObject):
    label = "Index Copernicus"
    field_name = "index_copernicus"


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
    label = u'Źródło'
    ops = EQUALITY_OPS_NONE
    model = Zrodlo
    field_name = 'zrodlo'

    def get_autocomplete_query(self, data):
        return Zrodlo.objects.fulltext_filter(data)


registry = create_registry(
    Rekord,
    TytulPracyQueryObject(),
    NazwiskoIImieQueryObject(),
    JednostkaQueryObject(),
    # Działa wadliwie i jest BEZ SENSU
    # Typ_OdpowiedzialnosciQueryObject(),
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

    AdnotacjeQueryObject(),
    DataUtworzeniaQueryObject(),
    ordering=[
        Ordering("", u"(nieistotne)"),
        Ordering("tytul_oryginalny", u"tytuł oryginalny"),
        Ordering("rok", u"rok"),
        Ordering("impact_factor", u"impact factor"),
        Ordering("punkty_kbn", u"punkty KBN"),
        Ordering("charakter_formalny__nazwa", u"charakter formalny"),
        Ordering("typ_kbn__nazwa", u"typ KBN"),
        Ordering("zrodlo__nazwa", u"źródło"),
        Ordering("pierwszy_autor__nazwisko", u"pierwszy autor"),
    ],
    report_types=[
        ReportType("list", "lista"),
        ReportType("table", "tabela"),
        ReportType("pkt_wewn", "punktacja sumaryczna z punktacją wewnętrzna"),
        ReportType("pkt_wewn_bez",
                   "punktacja sumaryczna bez punktacji wewnętrznej"),
        ReportType("numer_list", "numerowana lista z uwagami", public=False)
    ])