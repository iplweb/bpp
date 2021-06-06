# -*- encoding: utf-8 -*-
from django.conf import settings
from mptt.forms import TreeNodeChoiceFieldMixin
from mptt.settings import DEFAULT_LEVEL_INDICATOR
from taggit.models import Tag

from django.contrib.postgres.search import SearchQuery

from django.utils.itercompat import is_iterable

from bpp.models.konferencja import Konferencja
from bpp.models.openaccess import (
    Czas_Udostepnienia_OpenAccess,
    Licencja_OpenAccess,
    Wersja_Tekstu_OpenAccess,
)
from bpp.models.struktura import Wydzial

NULL_VALUE = "(brak wpisanej wartości)"

from django.db.models import Q
from django.db.models.expressions import F
from multiseek import logic
from multiseek.logic import (
    AUTOCOMPLETE,
    DIFFERENT,
    DIFFERENT_ALL,
    DIFFERENT_FEMALE,
    DIFFERENT_NONE,
    EQUAL,
    EQUAL_FEMALE,
    EQUAL_NONE,
    EQUALITY_OPS_ALL,
    EQUALITY_OPS_FEMALE,
    EQUALITY_OPS_MALE,
    EQUALITY_OPS_NONE,
    VALUE_LIST,
    AutocompleteQueryObject,
    BooleanQueryObject,
    DateQueryObject,
    DecimalQueryObject,
    IntegerQueryObject,
    Ordering,
    QueryObject,
    RangeQueryObject,
    ReportType,
    StringQueryObject,
    UnknownOperation,
    ValueListQueryObject,
    create_registry,
)

from bpp.models import (
    Autor,
    Autorzy,
    Charakter_Formalny,
    Dyscyplina_Naukowa,
    Jednostka,
    Jezyk,
    SlowaKluczoweView,
    Typ_Odpowiedzialnosci,
    Uczelnia,
    Wydawnictwo_Zwarte,
    Zewnetrzna_Baza_Danych,
    ZewnetrzneBazyDanychView,
    Zrodlo,
    const,
)
from bpp.models.cache import Rekord
from bpp.models.system import Typ_KBN

UNION = "równy+wspólny"
UNION_FEMALE = "równa+wspólna"
UNION_NONE = "równe+wspólne"
UNION_OPS_ALL = [UNION, UNION_FEMALE, UNION_NONE]


class TytulPracyQueryObject(StringQueryObject):
    label = "Tytuł pracy"
    field_name = "tytul_oryginalny"

    def real_query(self, value, operation):
        ret = super(StringQueryObject, self).real_query(
            value, operation, validate_operation=False
        )

        if ret is not None:
            return ret

        elif operation in [logic.CONTAINS, logic.NOT_CONTAINS]:
            if not value:
                return Q(pk=F("pk"))

            query = None

            if operation == logic.CONTAINS:
                value = [x.strip() for x in value.split(" ") if x.strip()]
                for elem in value:
                    elem = SearchQuery(elem, config="bpp_nazwy_wlasne")
                    if query is None:
                        query = elem
                        continue
                    query &= elem

            else:
                # Jeżeli "nie zawiera", to nie tokenizuj spacjami
                query = ~SearchQuery(value, config="bpp_nazwy_wlasne")

            ret = Q(search_index=query)

        elif operation in [logic.STARTS_WITH, logic.NOT_STARTS_WITH]:
            ret = Q(**{self.field_name + "__istartswith": value})

            if operation in [logic.NOT_STARTS_WITH]:
                ret = ~ret
        else:
            raise UnknownOperation(operation)

        return ret


class AdnotacjeQueryObject(StringQueryObject):
    label = "Adnotacje"
    field_name = "adnotacje"
    public = False


class DOIQueryObject(StringQueryObject):
    label = "DOI"
    field_name = "doi"
    public = False


class InformacjeQueryObject(StringQueryObject):
    label = "Informacje"
    field_name = "informacje"


class SzczegolyQueryObject(StringQueryObject):
    label = "Szczegóły"
    field_name = "szczegoly"


class UwagiQueryObject(StringQueryObject):
    label = "Uwagi"
    field_name = "uwagi"


class SlowaKluczoweQueryObject(AutocompleteQueryObject):
    type = AUTOCOMPLETE
    ops = [EQUAL_NONE, DIFFERENT_NONE]
    model = Tag
    search_fields = ["name"]
    url = "bpp:public-taggit-tag-autocomplete"
    label = "Słowa kluczowe"
    field_name = "slowa_kluczowe"

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(
                pk__in=SlowaKluczoweView.objects.filter(tag__name=value).values(
                    "rekord_id"
                )
            )

        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret

        return ret


class DataUtworzeniaQueryObject(DateQueryObject):
    label = "Data utworzenia"
    field_name = "utworzono"
    public = False

    def value_for_description(self, value):
        value = self.value_from_web(value)
        if value is None:
            return NULL_VALUE
        if is_iterable(value):
            return "od %s do %s" % (value[0], value[1])
        return str(value)


class OstatnioZmieniony(DataUtworzeniaQueryObject):
    label = "Ostatnio zmieniony"
    field_name = "ostatnio_zmieniony"
    public = False


class OstatnioZmienionyDlaPBN(DataUtworzeniaQueryObject):
    label = "Ostatnio zmieniony (dla PBN)"
    field_name = "ostatnio_zmieniony_dla_pbn"
    public = False


class ForeignKeyDescribeMixin:
    def value_for_description(self, value):
        if value is None:
            return NULL_VALUE

        return self.value_from_web(value) or "[powiązany obiekt został usunięty]"


class NazwiskoIImieQueryObject(ForeignKeyDescribeMixin, AutocompleteQueryObject):
    label = "Nazwisko i imię"
    type = AUTOCOMPLETE
    ops = [EQUAL_NONE, DIFFERENT_NONE, UNION_NONE]
    model = Autor
    search_fields = ["nazwisko", "imiona"]
    field_name = "autor"
    url = "bpp:public-autor-autocomplete"

    def real_query(self, value, operation):

        if operation in EQUALITY_OPS_ALL:
            ret = Q(autorzy__autor=value)

        elif operation in UNION_OPS_ALL:
            q = Autorzy.objects.filter(autor=value).values("rekord_id")

            ret = Q(pk__in=q)
        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret

        return ret


class WydawnictwoNadrzedneQueryObject(ForeignKeyDescribeMixin, AutocompleteQueryObject):
    label = "Wydawnictwo nadrzędne"
    type = AUTOCOMPLETE
    ops = [
        EQUAL_NONE,
        DIFFERENT_NONE,
    ]
    model = Wydawnictwo_Zwarte
    search_fields = [
        "tytul_oryginalny",
    ]
    field_name = "wydawnictwo_nadrzedne"
    url = "bpp:public-wydawnictwo-nadrzedne-autocomplete"

    def real_query(self, value, operation):

        if operation in EQUALITY_OPS_ALL:
            ret = Q(wydawnictwo_nadrzedne=value)

        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret

        return ret


class ORCIDQueryObject(StringQueryObject):
    label = "ORCID"
    ops = [EQUAL_NONE, DIFFERENT_NONE]
    field_name = "autorzy__autor__orcid"


class NazwiskoIImieWZakresieKolejnosci(NazwiskoIImieQueryObject):
    ops = [EQUAL, UNION_NONE]
    kolejnosc_gte = None
    kolejnosc_lt = None

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(
                autorzy__autor=value,
                autorzy__kolejnosc__gte=self.kolejnosc_gte,
                autorzy__kolejnosc__lt=self.kolejnosc_lt,
            )

        elif operation in UNION_OPS_ALL:
            q = Autorzy.objects.filter(
                autor=value,
                kolejnosc__gte=self.kolejnosc_gte,
                kolejnosc__lt=self.kolejnosc_lt,
            ).values("rekord_id")
            ret = Q(pk__in=q)

        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret

        return ret


class PierwszeNazwiskoIImie(NazwiskoIImieWZakresieKolejnosci):
    kolejnosc_gte = 0
    kolejnosc_lt = 1
    label = "Pierwsze nazwisko i imię"


class OstatnieNazwiskoIImie(NazwiskoIImieWZakresieKolejnosci):
    ops = [
        EQUAL,
    ]
    # bez operatora UNION, bo F('liczba_autorow') nie istnieje, gdy
    # generujemy zapytanie dla niego.
    kolejnosc_gte = F("liczba_autorow") - 1
    kolejnosc_lt = F("liczba_autorow")
    label = "Ostatnie nazwisko i imię"
    public = False


class NazwiskoIImie1do3(NazwiskoIImieWZakresieKolejnosci):
    kolejnosc_gte = 0
    kolejnosc_lt = 3
    label = "Nazwisko i imię (od 1 do 3)"
    public = False


class NazwiskoIImie1do5(NazwiskoIImieWZakresieKolejnosci):
    kolejnosc_gte = 0
    kolejnosc_lt = 5
    label = "Nazwisko i imię (od 1 do 5)"
    public = False


class TypOgolnyAutorQueryObject(NazwiskoIImieQueryObject):
    ops = [EQUAL, DIFFERENT, UNION]

    label = "Autor"
    typ_ogolny = const.TO_AUTOR

    def real_query(self, value, operation):

        if operation in EQUALITY_OPS_ALL:
            ret = Q(
                autorzy__autor=value,
                autorzy__typ_odpowiedzialnosci__typ_ogolny=self.typ_ogolny,
            )

        elif operation in UNION_OPS_ALL:
            q = Autorzy.objects.filter(
                autor=value, typ_odpowiedzialnosci__typ_ogolny=self.typ_ogolny
            ).values("rekord_id")
            ret = Q(pk__in=q)

        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret

        return ret


class TypOgolnyRedaktorQueryObject(TypOgolnyAutorQueryObject):
    typ_ogolny = const.TO_REDAKTOR
    label = "Redaktor"


class TypOgolnyTlumaczQueryObject(TypOgolnyAutorQueryObject):
    typ_ogolny = const.TO_TLUMACZ
    label = "Tłumacz"


class TypOgolnyRecenzentQueryObject(TypOgolnyAutorQueryObject):
    typ_ogolny = const.TO_RECENZENT
    label = "Recenzent"


class DyscyplinaQueryObject(ForeignKeyDescribeMixin, AutocompleteQueryObject):
    label = "Dyscyplina naukowa autora"
    type = AUTOCOMPLETE
    ops = [
        EQUAL_NONE,
    ]
    model = Dyscyplina_Naukowa
    field_name = "nazwa"
    url = "bpp:dyscyplina-autocomplete"

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(autorzy__dyscyplina_naukowa=value)
        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret
        return ret


class NazwaKonferencji(ForeignKeyDescribeMixin, AutocompleteQueryObject):
    label = "Konferencja"
    type = AUTOCOMPLETE
    ops = EQUALITY_OPS_FEMALE
    model = Konferencja
    search_fields = ["nazwa"]
    field_name = "konferencja"
    url = "bpp:public-konferencja-autocomplete"


class ZewnetrznaBazaDanychQueryObject(ForeignKeyDescribeMixin, AutocompleteQueryObject):
    label = "Zewnętrzna baza danych"
    type = AUTOCOMPLETE
    ops = [
        EQUAL_FEMALE,
    ]
    model = Zewnetrzna_Baza_Danych
    search_fields = ["nazwa"]
    url = "bpp:zewnetrzna-baza-danych-autocomplete"

    def real_query(self, value, operation, validate_operation=True):
        if operation in EQUALITY_OPS_ALL:
            q = ZewnetrzneBazyDanychView.objects.filter(baza=value).values("rekord_id")
            ret = Q(pk__in=q)
        else:
            raise UnknownOperation(operation)
        return ret


EQUAL_PLUS_SUB_FEMALE = "równa+podrzędne"
EQUAL_PLUS_SUB_UNION_FEMALE = "równa+podrzędne+wspólna"


class JednostkaQueryObject(ForeignKeyDescribeMixin, AutocompleteQueryObject):
    label = "Jednostka"
    type = AUTOCOMPLETE
    ops = [
        EQUAL_FEMALE,
        DIFFERENT_FEMALE,
        EQUAL_PLUS_SUB_FEMALE,
        UNION_FEMALE,
        EQUAL_PLUS_SUB_UNION_FEMALE,
    ]
    model = Jednostka
    search_fields = ["nazwa"]
    field_name = "jednostka"
    url = "bpp:jednostka-widoczna-autocomplete"

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(autorzy__jednostka=value)

        elif operation == EQUAL_PLUS_SUB_FEMALE:
            ret = Q(autorzy__jednostka__in=value.get_family())

        elif operation in EQUAL_PLUS_SUB_UNION_FEMALE:
            q = Autorzy.objects.filter(jednostka__in=value.get_family()).values(
                "rekord_id"
            )
            ret = Q(pk__in=q)

        elif operation in UNION_OPS_ALL:
            q = Autorzy.objects.filter(jednostka=value).values("rekord_id")
            ret = Q(pk__in=q)

        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret
        return ret


class WydzialQueryObject(ForeignKeyDescribeMixin, AutocompleteQueryObject):
    label = "Wydział"
    type = AUTOCOMPLETE
    ops = [EQUAL, DIFFERENT, UNION]
    model = Wydzial
    search_fields = ["nazwa"]
    field_name = "wydzial"
    url = "bpp:public-wydzial-autocomplete"

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(autorzy__jednostka__wydzial=value)

        elif operation in UNION_OPS_ALL:
            q = Autorzy.objects.filter(jednostka__wydzial=value).values("rekord_id")
            ret = Q(pk__in=q)

        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret

        return ret


class Typ_OdpowiedzialnosciQueryObject(QueryObject):
    label = "Typ odpowiedzialności"
    type = VALUE_LIST
    values = Typ_Odpowiedzialnosci.objects.all()
    ops = [EQUAL, DIFFERENT, UNION]
    field_name = "typ_odpowiedzialnosci"
    public = False

    def value_from_web(self, value):
        return Typ_Odpowiedzialnosci.objects.get(nazwa=value)

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(autorzy__typ_odpowiedzialnosci=value)

        elif operation in UNION_OPS_ALL:
            q = Autorzy.objects.filter(typ_odpowiedzialnosci=value).values("rekord_id")
            ret = Q(pk__in=q)

        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret

        return ret


class ZakresLatQueryObject(RangeQueryObject):
    label = "Zakres lat"
    field_name = "rok"


class JezykQueryObject(QueryObject):
    label = "Język"
    type = VALUE_LIST
    ops = EQUALITY_OPS_MALE
    values = Jezyk.objects.all()
    field_name = "jezyk"

    def value_from_web(self, value):
        return Jezyk.objects.get(nazwa=value)


class RokQueryObject(IntegerQueryObject):
    label = "Rok"
    field_name = "rok"


class ImpactQueryObject(DecimalQueryObject):
    label = "Impact factor"
    field_name = "impact_factor"


class LiczbaCytowanQueryObject(IntegerQueryObject):
    label = "Liczba cytowań"
    field_name = "liczba_cytowan"


class LiczbaAutorowQueryObject(IntegerQueryObject):
    label = "Liczba autorów"
    field_name = "liczba_autorow"


class KCImpactQueryObject(ImpactQueryObject):
    field_name = "kc_impact_factor"
    label = "KC: Impact factor"
    public = False


class PunktacjaWewnetrznaEnabledMixin:
    def enabled(self, request):
        if self.public:
            return settings.UZYWAJ_PUNKTACJI_WEWNETRZNEJ
        return ReportType.enabled(self, request)


class PunktacjaWewnetrznaQueryObject(
    PunktacjaWewnetrznaEnabledMixin, DecimalQueryObject
):
    label = "Punktacja wewnętrzna"
    field_name = "punktacja_wewnetrzna"


class PunktacjaSNIP(DecimalQueryObject):
    label = "Punktacja SNIP"
    field_name = "punktacja_snip"


class PunktyKBNQueryObject(DecimalQueryObject):
    label = "Punkty PK"
    field_name = "punkty_kbn"


class KCPunktyKBNQueryObject(PunktyKBNQueryObject):
    label = "KC: Punkty PK"
    field_name = "kc_punkty_kbn"
    public = False


class IndexCopernicusQueryObject(DecimalQueryObject):
    label = "Index Copernicus"
    field_name = "index_copernicus"

    def enabled(self, request):
        u = Uczelnia.objects.first()
        if u is not None:
            return u.pokazuj_index_copernicus
        return True


class LiczbaZnakowWydawniczychQueryObject(IntegerQueryObject):
    label = "Liczba znaków wydawniczych"
    field_name = "liczba_znakow_wydawniczych"


class TypRekorduObject(ValueListQueryObject):
    label = "Typ rekordu"
    values = ["publikacje", "streszczenia", "inne"]
    ops = [EQUAL, DIFFERENT]

    def value_from_web(self, value):
        if value not in self.values:
            return
        return value

    def real_query(self, value, operation):
        if value == "publikacje":
            charaktery = Charakter_Formalny.objects.filter(publikacja=True)
        elif value == "streszczenia":
            charaktery = Charakter_Formalny.objects.filter(streszczenie=True)
        else:
            charaktery = (
                Charakter_Formalny.objects.all()
                .exclude(streszczenie=True)
                .exclude(publikacja=True)
            )

        q = Q(**{"charakter_formalny__in": charaktery})
        if operation == DIFFERENT:
            return ~q
        return q


class CharakterOgolnyQueryObject(ValueListQueryObject):
    label = "Charakter formalny ogólny"
    values = ["artykuł", "rozdział", "książka", "inne"]
    ops = [EQUAL, DIFFERENT]

    def value_from_web(self, value):
        if value not in self.values:
            return
        return value

    def real_query(self, value, operation):
        if value == "artykuł":
            charaktery = Charakter_Formalny.objects.filter(
                charakter_ogolny=const.CHARAKTER_OGOLNY_ARTYKUL
            )
        elif value == "rozdział":
            charaktery = Charakter_Formalny.objects.filter(
                charakter_ogolny=const.CHARAKTER_OGOLNY_ROZDZIAL
            )
        elif value == "książka":
            charaktery = Charakter_Formalny.objects.filter(
                charakter_ogolny=const.CHARAKTER_OGOLNY_KSIAZKA
            )
        elif value == "inne":
            charaktery = Charakter_Formalny.objects.filter(
                charakter_ogolny=const.CHARAKTER_OGOLNY_INNE
            )
        else:
            raise NotImplementedError()

        q = Q(**{"charakter_formalny__in": charaktery})
        if operation == DIFFERENT:
            return ~q
        return q


class CharakterFormalnyQueryObject(TreeNodeChoiceFieldMixin, ValueListQueryObject):
    field_name = "charakter_formalny"
    label = "Charakter formalny"

    def _values(self):
        for elem in self.queryset:
            yield self.label_from_instance(elem)

    values = property(_values)

    def value_from_web(self, value):
        return Charakter_Formalny.objects.get(nazwa=value.lstrip("-").lstrip(" "))

    def __init__(self, *args, **kwargs):
        ValueListQueryObject.__init__(self, *args, **kwargs)

        self.level_indicator = kwargs.pop("level_indicator", DEFAULT_LEVEL_INDICATOR)
        queryset = Charakter_Formalny.objects.all()
        # if a queryset is supplied, enforce ordering
        if hasattr(queryset, "model"):
            mptt_opts = queryset.model._mptt_meta
            queryset = queryset.order_by(mptt_opts.tree_id_attr, mptt_opts.left_attr)
        self.queryset = queryset

    def real_query(self, value, operation, validate_operation=True):
        ret = None

        if operation in [str(x) for x in EQUALITY_OPS_ALL]:
            ret = Q(
                **{self.field_name + "__in": value.get_descendants(include_self=True)}
            )

        else:
            if validate_operation:
                raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret

        return ret


class OpenaccessWersjaTekstuQueryObject(ValueListQueryObject):
    field_name = "openaccess_wersja_tekstu"
    values = Wersja_Tekstu_OpenAccess.objects.all()
    label = "OpenAccess: wersja tekstu"

    def value_from_web(self, value):
        return Wersja_Tekstu_OpenAccess.objects.get(nazwa=value)


class OpenaccessLicencjaQueryObject(ValueListQueryObject):
    field_name = "openaccess_licencja"
    values = Licencja_OpenAccess.objects.all()
    label = "OpenAccess: licencja"

    def value_from_web(self, value):
        return Licencja_OpenAccess.objects.get(nazwa=value)


class OpenaccessCzasPublikacjiQueryObject(ValueListQueryObject):
    field_name = "openaccess_czas_publikacji"
    values = Czas_Udostepnienia_OpenAccess.objects.all()
    label = "OpenAccess: czas udostępnienia"

    def value_from_web(self, value):
        return Czas_Udostepnienia_OpenAccess.objects.get(nazwa=value)


class TypKBNQueryObject(ValueListQueryObject):
    field_name = "typ_kbn"
    values = Typ_KBN.objects.all()
    label = "Typ KBN"

    def value_from_web(self, value):
        return Typ_KBN.objects.get(nazwa=value)


class ZrodloQueryObject(AutocompleteQueryObject):
    label = "Źródło"
    ops = EQUALITY_OPS_NONE
    model = Zrodlo
    field_name = "zrodlo"
    url = "bpp:zrodlo-autocomplete"


class RecenzowanaQueryObject(BooleanQueryObject):
    ops = EQUALITY_OPS_NONE
    field_name = "recenzowana"
    label = "Praca recenzowana"


class BazaWOS(BooleanQueryObject):
    ops = EQUALITY_OPS_NONE
    field_name = "konferencja__baza_wos"
    label = "Konferencja w bazie Web of Science"


class BazaSCOPUS(BooleanQueryObject):
    ops = EQUALITY_OPS_NONE
    field_name = "konferencja__baza_scopus"
    label = "Konferencja w bazie Scopus"


class RodzajKonferenckjiQueryObject(ValueListQueryObject):
    label = "Rodzaj konferencji"
    values = ["krajowa", "międzynarodowa", "lokalna"]

    def value_from_web(self, value):
        if value not in self.values:
            return
        return value

    def real_query(self, value, operation):
        if value == "krajowa":
            tk = Konferencja.TK_KRAJOWA
        elif value == "międzynarodowa":
            tk = Konferencja.TK_MIEDZYNARODOWA
        else:
            tk = Konferencja.TK_LOKALNA

        q = Q(**{"konferencja__typ_konferencji": tk})
        if operation == DIFFERENT:
            return ~q
        return q


class ObcaJednostkaQueryObject(BooleanQueryObject):
    label = "Obca jednostka"
    ops = EQUALITY_OPS_FEMALE
    public = False

    def real_query(self, value, operation):
        value = not value

        if operation in EQUALITY_OPS_ALL:
            ret = Q(autorzy__jednostka__skupia_pracownikow=value)
        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret

        return ret


class AfiliujeQueryObject(BooleanQueryObject):
    label = "Afiliuje"
    ops = [
        EQUAL,
    ]
    public = False

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(autorzy__afiliuje=value)
        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret

        return ret


class DyscyplinaUstawionaQueryObject(BooleanQueryObject):
    label = "Dyscyplina ustawiona"
    ops = EQUALITY_OPS_FEMALE
    public = False

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            if value:
                ret = ~Q(autorzy__dyscyplina_naukowa=None)
            else:
                ret = Q(autorzy__dyscyplina_naukowa=None)
        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret

        return ret


class StronaWWWUstawionaQueryObject(BooleanQueryObject):
    label = "Strona WWW ustawiona"
    ops = [
        EQUAL_FEMALE,
    ]
    public = False

    def real_query(self, value, operation):
        if value:
            ret = Q(
                Q(~Q(public_www="") & Q(public_www__isnull=False))
                | Q(~Q(www="") & Q(www__isnull=False))
            )
        else:
            ret = Q(
                Q(Q(public_www="") | Q(public_www__isnull=True))
                & Q(Q(www="") | Q(www__isnull=True))
            )

        return ret


class LicencjaOpenAccessUstawionaQueryObject(BooleanQueryObject):
    label = "Licencja OpenAccess ustawiona"
    ops = EQUALITY_OPS_FEMALE
    public = False

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            if value:
                ret = Q(openaccess_licencja__isnull=False)
            else:
                ret = Q(openaccess_licencja__isnull=True)
        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret

        return ret


class PublicDostepDniaQueryObject(BooleanQueryObject):
    label = "Dostęp dnia ustawiony"
    field_name = "public_dostep_dnia"
    public = False

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            if value:
                ret = ~Q(public_dostep_dnia=None)
            else:
                ret = Q(public_dostep_dnia=None)
        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret

        return ret


multiseek_fields = [
    TytulPracyQueryObject(),
    NazwiskoIImieQueryObject(),
    JednostkaQueryObject(),
    WydzialQueryObject(),
    Typ_OdpowiedzialnosciQueryObject(),
    TypOgolnyAutorQueryObject(),
    TypOgolnyRedaktorQueryObject(),
    TypOgolnyTlumaczQueryObject(),
    TypOgolnyRecenzentQueryObject(),
    ZakresLatQueryObject(),
    JezykQueryObject(),
    RokQueryObject(),
    TypRekorduObject(),
    CharakterFormalnyQueryObject(),
    CharakterOgolnyQueryObject(),
    TypKBNQueryObject(),
    ZrodloQueryObject(),
    WydawnictwoNadrzedneQueryObject(),
    PierwszeNazwiskoIImie(),
    NazwiskoIImie1do3(),
    NazwiskoIImie1do5(),
    OstatnieNazwiskoIImie(),
    ORCIDQueryObject(),
    ImpactQueryObject(),
    LiczbaCytowanQueryObject(),
    LiczbaAutorowQueryObject(),
    PunktyKBNQueryObject(),
    IndexCopernicusQueryObject(),
    PunktacjaSNIP(),
    PunktacjaWewnetrznaQueryObject(),
    KCImpactQueryObject(),
    KCPunktyKBNQueryObject(),
    InformacjeQueryObject(),
    SzczegolyQueryObject(),
    UwagiQueryObject(),
    SlowaKluczoweQueryObject(),
    AdnotacjeQueryObject(),
    DataUtworzeniaQueryObject(),
    OstatnioZmieniony(),
    OstatnioZmienionyDlaPBN(),
    RecenzowanaQueryObject(),
    LiczbaZnakowWydawniczychQueryObject(),
    NazwaKonferencji(),
    RodzajKonferenckjiQueryObject(),
    BazaWOS(),
    BazaSCOPUS(),
    OpenaccessWersjaTekstuQueryObject(),
    OpenaccessLicencjaQueryObject(),
    OpenaccessCzasPublikacjiQueryObject(),
    DyscyplinaQueryObject(),
    ZewnetrznaBazaDanychQueryObject(),
    ObcaJednostkaQueryObject(),
    AfiliujeQueryObject(),
    DyscyplinaUstawionaQueryObject(),
    LicencjaOpenAccessUstawionaQueryObject(),
    PublicDostepDniaQueryObject(),
    StronaWWWUstawionaQueryObject(),
    DOIQueryObject(),
]


class PunktacjaWewnetrznaReportType(PunktacjaWewnetrznaEnabledMixin, ReportType):
    pass


multiseek_report_types = [
    ReportType("list", "lista"),
    ReportType("table", "tabela"),
    PunktacjaWewnetrznaReportType(
        "pkt_wewn", "punktacja sumaryczna z punktacją wewnętrzna"
    ),
    ReportType("pkt_wewn_bez", "punktacja sumaryczna"),
    ReportType("numer_list", "numerowana lista z uwagami", public=False),
    ReportType("table_cytowania", "tabela z liczbą cytowań", public=False),
    PunktacjaWewnetrznaReportType(
        "pkt_wewn_cytowania",
        "punktacja sumaryczna z punktacją wewnętrzna z liczbą cytowań",
        public=False,
    ),
    ReportType(
        "pkt_wewn_bez_cytowania", "punktacja sumaryczna z liczbą cytowań", public=False
    ),
]

registry = create_registry(
    Rekord,
    *multiseek_fields,
    ordering=[
        Ordering("", "(nieistotne)"),
        Ordering("tytul_oryginalny", "tytuł oryginalny"),
        Ordering("rok", "rok"),
        Ordering("impact_factor", "impact factor"),
        Ordering("liczba_cytowan", "liczba cytowań"),
        Ordering("liczba_autorow", "liczba autorów"),
        Ordering("punkty_kbn", "punkty PK"),
        Ordering("charakter_formalny__nazwa", "charakter formalny"),
        Ordering("typ_kbn__nazwa", "typ KBN"),
        Ordering("zrodlo_lub_nadrzedne", "źródło/wyd.nadrz."),
        Ordering("utworzono", "utworzono"),
        Ordering("ostatnio_zmieniony", "ostatnio zmieniony"),
        Ordering("ostatnio_zmieniony_dla_pbn", "ostatnio zmieniony (dla PBN)"),
    ],
    default_ordering=["-rok", "", ""],
    report_types=multiseek_report_types
)
