from django.conf import settings
from mptt.forms import TreeNodeChoiceFieldMixin
from mptt.settings import DEFAULT_LEVEL_INDICATOR
from taggit.models import Tag

from .mixins import BppMultiseekVisibilityMixin

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
    QueryObject,
    RangeQueryObject,
    ReportType,
    StringQueryObject,
    UnknownOperation,
    ValueListQueryObject,
)

from .. import const

from bpp.models import (
    Autor,
    Autorzy,
    Charakter_Formalny,
    Dyscyplina_Naukowa,
    Jednostka,
    Jezyk,
    Kierunek_Studiow,
    SlowaKluczoweView,
    Status_Korekty,
    Typ_Odpowiedzialnosci,
    Uczelnia,
    Wydawnictwo_Zwarte,
    Zewnetrzna_Baza_Danych,
    ZewnetrzneBazyDanychView,
    Zrodlo,
)
from bpp.models.system import Typ_KBN

UNION = "równy+wspólny"
UNION_FEMALE = "równa+wspólna"
UNION_NONE = "równe+wspólne"
UNION_OPS_ALL = [UNION, UNION_FEMALE, UNION_NONE]


class TytulPracyQueryObject(BppMultiseekVisibilityMixin, StringQueryObject):
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


class AdnotacjeQueryObject(BppMultiseekVisibilityMixin, StringQueryObject):
    label = "Adnotacje"
    field_name = "adnotacje"
    public = False


class DOIQueryObject(BppMultiseekVisibilityMixin, StringQueryObject):
    label = "DOI"
    field_name = "doi"
    public = False


class InformacjeQueryObject(BppMultiseekVisibilityMixin, StringQueryObject):
    label = "Informacje"
    field_name = "informacje"


class SzczegolyQueryObject(BppMultiseekVisibilityMixin, StringQueryObject):
    label = "Szczegóły"
    field_name = "szczegoly"


class UwagiQueryObject(BppMultiseekVisibilityMixin, StringQueryObject):
    label = "Uwagi"
    field_name = "uwagi"


class SlowaKluczoweQueryObject(BppMultiseekVisibilityMixin, AutocompleteQueryObject):
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


class DataUtworzeniaQueryObject(BppMultiseekVisibilityMixin, DateQueryObject):
    label = "Data utworzenia"
    field_name = "utworzono"
    public = False

    def value_for_description(self, value):
        value = self.value_from_web(value)
        if value is None:
            return NULL_VALUE
        if is_iterable(value):
            return f"od {value[0]} do {value[1]}"
        return str(value)


class OstatnioZmieniony(DataUtworzeniaQueryObject):
    label = "Ostatnio zmieniony"
    field_name = "ostatnio_zmieniony"
    public = False


class ForeignKeyDescribeMixin:
    def value_for_description(self, value):
        if value is None:
            return NULL_VALUE

        return self.value_from_web(value) or "[powiązany obiekt został usunięty]"


class NazwiskoIImieQueryObject(
    BppMultiseekVisibilityMixin, ForeignKeyDescribeMixin, AutocompleteQueryObject
):
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


class WydawnictwoNadrzedneQueryObject(
    BppMultiseekVisibilityMixin, ForeignKeyDescribeMixin, AutocompleteQueryObject
):
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


class StatusKorektyQueryObject(
    BppMultiseekVisibilityMixin, ForeignKeyDescribeMixin, AutocompleteQueryObject
):
    label = "Status korekty"
    type = AUTOCOMPLETE
    ops = [
        EQUAL_NONE,
        DIFFERENT_NONE,
    ]
    model = Status_Korekty
    search_fields = [
        "status_korekty",
    ]
    field_name = "status_korekty"
    url = "bpp:public-status-korekty-autocomplete"

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(status_korekty=value)

        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret

        return ret


class ORCIDQueryObject(BppMultiseekVisibilityMixin, StringQueryObject):
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
    field_name = "naz_im_pierwsz"


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
    field_name = "naz_im_ost"


class NazwiskoIImie1do3(NazwiskoIImieWZakresieKolejnosci):
    kolejnosc_gte = 0
    kolejnosc_lt = 3
    label = "Nazwisko i imię (od 1 do 3)"
    public = False
    field_name = "naz_im_1_3"


class NazwiskoIImie1do5(NazwiskoIImieWZakresieKolejnosci):
    kolejnosc_gte = 0
    kolejnosc_lt = 5
    label = "Nazwisko i imię (od 1 do 5)"
    public = False
    field_name = "naz_im_1_5"


class TypOgolnyAutorQueryObject(NazwiskoIImieQueryObject):
    ops = [EQUAL, DIFFERENT, UNION]

    label = "Autor"
    typ_ogolny = const.TO_AUTOR
    field_name = "typ_og_autor"

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
    field_name = "typ_og_redaktor"


class TypOgolnyTlumaczQueryObject(TypOgolnyAutorQueryObject):
    typ_ogolny = const.TO_TLUMACZ
    label = "Tłumacz"
    field_name = "typ_og_tlumacz"


class TypOgolnyRecenzentQueryObject(TypOgolnyAutorQueryObject):
    typ_ogolny = const.TO_RECENZENT
    label = "Recenzent"
    field_name = "typ_og_recenzent"


class DyscyplinaQueryObject(
    BppMultiseekVisibilityMixin, ForeignKeyDescribeMixin, AutocompleteQueryObject
):
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


class NazwaKonferencji(
    BppMultiseekVisibilityMixin, ForeignKeyDescribeMixin, AutocompleteQueryObject
):
    label = "Konferencja"
    type = AUTOCOMPLETE
    ops = EQUALITY_OPS_FEMALE
    model = Konferencja
    search_fields = ["nazwa"]
    field_name = "konferencja"
    url = "bpp:public-konferencja-autocomplete"


class ZewnetrznaBazaDanychQueryObject(
    BppMultiseekVisibilityMixin, ForeignKeyDescribeMixin, AutocompleteQueryObject
):
    label = "Zewnętrzna baza danych"
    field_name = "zewn_baza_danych"
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


class JednostkaQueryObject(
    BppMultiseekVisibilityMixin, ForeignKeyDescribeMixin, AutocompleteQueryObject
):
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


class AktualnaJednostkaAutoraQueryObject(JednostkaQueryObject):
    label = "Aktualna jednostka dowolnego autora"
    type = AUTOCOMPLETE
    ops = [
        EQUAL_FEMALE,
        DIFFERENT_FEMALE,
        EQUAL_PLUS_SUB_FEMALE,
    ]
    model = Jednostka
    search_fields = ["nazwa"]
    field_name = "aktualna_jednostka"
    url = "bpp:jednostka-widoczna-autocomplete"

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(autorzy__autor__aktualna_jednostka=value)

        elif operation == EQUAL_PLUS_SUB_FEMALE:
            ret = Q(autorzy__autor__aktualna_jednostka__in=value.get_family())

        elif operation in EQUAL_PLUS_SUB_UNION_FEMALE:
            q = Autorzy.objects.filter(
                autor__aktualna_jednostka__in=value.get_family()
            ).values("rekord_id")
            ret = Q(pk__in=q)

        elif operation in UNION_OPS_ALL:
            q = Autorzy.objects.filter(autor__aktualna_jednostka=value).values(
                "rekord_id"
            )
            ret = Q(pk__in=q)

        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret
        return ret


class PierwszaJednostkaQueryObject(JednostkaQueryObject):
    ops = [
        EQUAL_FEMALE,
        DIFFERENT_FEMALE,
        EQUAL_PLUS_SUB_FEMALE,
        UNION_FEMALE,
        EQUAL_PLUS_SUB_UNION_FEMALE,
    ]
    label = "Pierwsza jednostka"
    field_name = "pierwsza_jednostka"

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(autorzy__jednostka=value, autorzy__kolejnosc=0)

        elif operation == EQUAL_PLUS_SUB_FEMALE:
            ret = Q(autorzy__jednostka__in=value.get_family(), autorzy__kolejnosc=0)

        elif operation in EQUAL_PLUS_SUB_UNION_FEMALE:
            q = Autorzy.objects.filter(
                jednostka__in=value.get_family(), kolejnosc=0
            ).values("rekord_id")
            ret = Q(pk__in=q)

        elif operation in UNION_OPS_ALL:
            q = Autorzy.objects.filter(jednostka=value, kolejnosc=0).values("rekord_id")
            ret = Q(pk__in=q)

        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret
        return ret


class WydzialQueryObject(
    BppMultiseekVisibilityMixin, ForeignKeyDescribeMixin, AutocompleteQueryObject
):
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


class PierwszyWydzialQueryObject(WydzialQueryObject):
    label = "Pierwszy wydział"
    field_name = "pierwszy_wydzial"

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(autorzy__jednostka__wydzial=value, autorzy__kolejnosc=0)

        elif operation in UNION_OPS_ALL:
            q = Autorzy.objects.filter(jednostka__wydzial=value, kolejnosc=0).values(
                "rekord_id"
            )
            ret = Q(pk__in=q)

        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret

        return ret


class Typ_OdpowiedzialnosciQueryObject(BppMultiseekVisibilityMixin, QueryObject):
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


class ZakresLatQueryObject(BppMultiseekVisibilityMixin, RangeQueryObject):
    label = "Zakres lat"
    field_name = "rok"
    bpp_multiseek_visibility_field_name = "zakres_lat"


class JezykQueryObject(BppMultiseekVisibilityMixin, QueryObject):
    label = "Język"
    type = VALUE_LIST
    ops = EQUALITY_OPS_MALE
    values = Jezyk.objects.all()
    field_name = "jezyk"

    def value_from_web(self, value):
        return Jezyk.objects.get(nazwa=value)


class RokQueryObject(BppMultiseekVisibilityMixin, IntegerQueryObject):
    label = "Rok"
    field_name = "rok"


class ImpactQueryObject(BppMultiseekVisibilityMixin, DecimalQueryObject):
    label = "Impact factor"
    field_name = "impact_factor"


class LiczbaCytowanQueryObject(BppMultiseekVisibilityMixin, IntegerQueryObject):
    label = "Liczba cytowań"
    field_name = "liczba_cytowan"


class LiczbaAutorowQueryObject(BppMultiseekVisibilityMixin, IntegerQueryObject):
    label = "Liczba autorów"
    field_name = "liczba_autorow"


class PunktacjaWewnetrznaEnabledMixin:
    def option_enabled(self, request):
        return settings.UZYWAJ_PUNKTACJI_WEWNETRZNEJ


class PunktacjaWewnetrznaQueryObject(
    BppMultiseekVisibilityMixin, PunktacjaWewnetrznaEnabledMixin, DecimalQueryObject
):
    label = "Punktacja wewnętrzna"
    field_name = "punktacja_wewnetrzna"


class PunktacjaSNIP(BppMultiseekVisibilityMixin, DecimalQueryObject):
    label = "Punktacja SNIP"
    field_name = "punktacja_snip"


class PunktyKBNQueryObject(BppMultiseekVisibilityMixin, DecimalQueryObject):
    label = "Punkty MNiSW/MEiN"
    field_name = "punkty_kbn"


class IndexCopernicusQueryObject(BppMultiseekVisibilityMixin, DecimalQueryObject):
    label = "Index Copernicus"
    field_name = "index_copernicus"

    def option_enabled(self):
        u = Uczelnia.objects.get_default()
        if u is not None:
            return u.pokazuj_index_copernicus
        return True


class LiczbaZnakowWydawniczychQueryObject(
    BppMultiseekVisibilityMixin, IntegerQueryObject
):
    label = "Liczba znaków wydawniczych"
    field_name = "liczba_znakow_wydawniczych"


class TypRekorduObject(BppMultiseekVisibilityMixin, ValueListQueryObject):
    label = "Typ rekordu"
    field_name = "typ_rekordu"
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


class CharakterOgolnyQueryObject(BppMultiseekVisibilityMixin, ValueListQueryObject):
    label = "Charakter formalny ogólny"
    field_name = "charakter_formalny_ogolny"
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


class CharakterFormalnyQueryObject(
    BppMultiseekVisibilityMixin, TreeNodeChoiceFieldMixin, ValueListQueryObject
):
    field_name = "charakter_formalny"
    label = "Charakter formalny"

    start_level = 0

    def _values(self):
        for elem in self.queryset:
            yield self.label_from_instance(elem)

    values = property(_values)

    def value_from_web(self, value):
        if value is None:
            return None
        return Charakter_Formalny.objects.get(nazwa=value.lstrip("-").lstrip(" "))

    def __init__(self, *args, **kwargs):
        ValueListQueryObject.__init__(self, *args, **kwargs)

        self.level_indicator = kwargs.pop("level_indicator", DEFAULT_LEVEL_INDICATOR)

    @property
    def queryset(self):
        queryset = Charakter_Formalny.objects.all()
        # if a queryset is supplied, enforce ordering
        if hasattr(queryset, "model"):
            mptt_opts = queryset.model._mptt_meta
            queryset = queryset.order_by(mptt_opts.tree_id_attr, mptt_opts.left_attr)
        return queryset
        # self.queryset = queryset

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


class OpenaccessWersjaTekstuQueryObject(
    BppMultiseekVisibilityMixin, ValueListQueryObject
):
    field_name = "openaccess_wersja_tekstu"
    values = Wersja_Tekstu_OpenAccess.objects.all()
    label = "OpenAccess: wersja tekstu"

    def value_from_web(self, value):
        return Wersja_Tekstu_OpenAccess.objects.get(nazwa=value)


class OpenaccessLicencjaQueryObject(BppMultiseekVisibilityMixin, ValueListQueryObject):
    field_name = "openaccess_licencja"
    values = Licencja_OpenAccess.objects.all()
    label = "OpenAccess: licencja"

    def value_from_web(self, value):
        return Licencja_OpenAccess.objects.get(nazwa=value)


class OpenaccessCzasPublikacjiQueryObject(
    BppMultiseekVisibilityMixin, ValueListQueryObject
):
    field_name = "openaccess_czas_publikacji"
    values = Czas_Udostepnienia_OpenAccess.objects.all()
    label = "OpenAccess: czas udostępnienia"

    def value_from_web(self, value):
        return Czas_Udostepnienia_OpenAccess.objects.get(nazwa=value)


class TypKBNQueryObject(BppMultiseekVisibilityMixin, ValueListQueryObject):
    field_name = "typ_kbn"
    values = Typ_KBN.objects.all()
    label = "Typ MNiSW/MEiN"

    def value_from_web(self, value):
        return Typ_KBN.objects.get(nazwa=value)


class ZrodloQueryObject(BppMultiseekVisibilityMixin, AutocompleteQueryObject):
    label = "Źródło"
    ops = EQUALITY_OPS_NONE
    model = Zrodlo
    field_name = "zrodlo"
    url = "bpp:zrodlo-autocomplete"


class RecenzowanaQueryObject(BppMultiseekVisibilityMixin, BooleanQueryObject):
    ops = EQUALITY_OPS_NONE
    field_name = "recenzowana"
    label = "Praca recenzowana"


class BazaWOS(BppMultiseekVisibilityMixin, BooleanQueryObject):
    ops = EQUALITY_OPS_NONE
    field_name = "konferencja__baza_wos"
    label = "Konferencja w bazie Web of Science"


class BazaSCOPUS(BppMultiseekVisibilityMixin, BooleanQueryObject):
    ops = EQUALITY_OPS_NONE
    field_name = "konferencja__baza_scopus"
    label = "Konferencja w bazie Scopus"


class RodzajKonferenckjiQueryObject(BppMultiseekVisibilityMixin, ValueListQueryObject):
    label = "Rodzaj konferencji"
    field_name = "rodzaj_konferencji"
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


class RodzajJednostkiQueryObject(BppMultiseekVisibilityMixin, ValueListQueryObject):
    label = "Rodzaj jednostki"
    field_name = "rodzaj_jednostki"
    values = Jednostka.RODZAJ_JEDNOSTKI.labels

    def value_from_web(self, value):
        if value not in self.values:
            return
        return value

    def real_query(self, value, operation):
        if value == Jednostka.RODZAJ_JEDNOSTKI.NORMALNA.label:
            tk = Jednostka.RODZAJ_JEDNOSTKI.NORMALNA.value
        else:
            tk = Jednostka.RODZAJ_JEDNOSTKI.KOLO_NAUKOWE.value

        q = Q(**{"autorzy__jednostka__rodzaj_jednostki": tk})
        if operation == DIFFERENT:
            return ~q
        return q


class ObcaJednostkaQueryObject(BppMultiseekVisibilityMixin, BooleanQueryObject):
    label = "Obca jednostka"
    field_name = "obca_jednostka"
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


class AfiliujeQueryObject(BppMultiseekVisibilityMixin, BooleanQueryObject):
    label = "Afiliuje"
    field_name = "afiliuje"
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


class DyscyplinaUstawionaQueryObject(BppMultiseekVisibilityMixin, BooleanQueryObject):
    label = "Dyscyplina ustawiona"
    field_name = "dyscyplina_ustawiona"
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


class StronaWWWUstawionaQueryObject(BppMultiseekVisibilityMixin, BooleanQueryObject):
    label = "Strona WWW ustawiona"
    field_name = "www_ustawiona"
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


class LicencjaOpenAccessUstawionaQueryObject(
    BppMultiseekVisibilityMixin, BooleanQueryObject
):
    label = "OpenAccess: licencja ustawiona"
    field_name = "lo_ustawiona"
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


class PublicDostepDniaQueryObject(BppMultiseekVisibilityMixin, BooleanQueryObject):
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


class KierunekStudiowQueryObject(
    BppMultiseekVisibilityMixin, ForeignKeyDescribeMixin, AutocompleteQueryObject
):
    label = "Kierunek studiów"
    type = AUTOCOMPLETE
    ops = [
        EQUAL,
        DIFFERENT,
        UNION,
    ]
    model = Kierunek_Studiow
    search_fields = ["nazwa"]
    field_name = "kierunek_studiow"
    url = "bpp:kierunek-studiow-autocomplete"

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(autorzy__kierunek_studiow=value)

        elif operation in UNION_OPS_ALL:
            q = Autorzy.objects.filter(kierunek_studiow=value).values("rekord_id")
            ret = Q(pk__in=q)

        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret
        return ret


class OswiadczenieKENQueryObject(BppMultiseekVisibilityMixin, BooleanQueryObject):
    label = "Oświadczenie KEN"
    ops = [
        EQUAL,
        DIFFERENT,
        UNION,
    ]
    field_name = "oswiadczenie_ken"

    def real_query(self, value, operation):
        if operation in EQUALITY_OPS_ALL:
            ret = Q(autorzy__oswiadczenie_ken=value)

        elif operation in UNION_OPS_ALL:
            q = Autorzy.objects.filter(oswiadczenie_ken=value).values("rekord_id")
            ret = Q(pk__in=q)

        else:
            raise UnknownOperation(operation)

        if operation in DIFFERENT_ALL:
            return ~ret
        return ret

    def enabled(self, request=None):
        if getattr(settings, "BPP_POKAZUJ_OSWIADCZENIE_KEN", False):
            return super().enabled(request)
        return False


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
    PierwszaJednostkaQueryObject(),
    PierwszyWydzialQueryObject(),
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
    InformacjeQueryObject(),
    SzczegolyQueryObject(),
    UwagiQueryObject(),
    SlowaKluczoweQueryObject(),
    AdnotacjeQueryObject(),
    DataUtworzeniaQueryObject(),
    OstatnioZmieniony(),
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
    AktualnaJednostkaAutoraQueryObject(),
    RodzajJednostkiQueryObject(),
    KierunekStudiowQueryObject(),
    OswiadczenieKENQueryObject(),
    StatusKorektyQueryObject(),
]


class PunktacjaWewnetrznaReportType(PunktacjaWewnetrznaEnabledMixin, ReportType):
    pass
