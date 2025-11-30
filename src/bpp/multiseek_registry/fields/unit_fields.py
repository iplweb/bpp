"""Unit/department-related query objects."""

from django.db.models import Q
from multiseek.logic import (
    AUTOCOMPLETE,
    DIFFERENT,
    DIFFERENT_ALL,
    DIFFERENT_FEMALE,
    EQUAL,
    EQUAL_FEMALE,
    EQUALITY_OPS_ALL,
    AutocompleteQueryObject,
    UnknownOperation,
    ValueListQueryObject,
)

from bpp.models import Autorzy, Jednostka
from bpp.models.struktura import Wydzial
from bpp.multiseek_registry.mixins import BppMultiseekVisibilityMixin

from .author_fields import ForeignKeyDescribeMixin
from .constants import (
    EQUAL_PLUS_SUB_FEMALE,
    EQUAL_PLUS_SUB_UNION_FEMALE,
    UNION,
    UNION_FEMALE,
    UNION_OPS_ALL,
)


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
