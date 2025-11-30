"""Boolean feature query objects."""

from django.db.models import Q
from multiseek.logic import (
    AUTOCOMPLETE,
    DIFFERENT,
    DIFFERENT_ALL,
    EQUAL,
    EQUAL_FEMALE,
    EQUALITY_OPS_ALL,
    EQUALITY_OPS_FEMALE,
    AutocompleteQueryObject,
    BooleanQueryObject,
    UnknownOperation,
)

from bpp.models import Autorzy, Kierunek_Studiow
from bpp.multiseek_registry.mixins import BppMultiseekVisibilityMixin

from .author_fields import ForeignKeyDescribeMixin
from .constants import UNION, UNION_OPS_ALL
from .factories import create_boolean_query_object

# Simple boolean query objects created with factory functions
RecenzowanaQueryObject = create_boolean_query_object("Praca recenzowana", "recenzowana")
BazaWOS = create_boolean_query_object(
    "Konferencja w bazie Web of Science", "konferencja__baza_wos"
)
BazaSCOPUS = create_boolean_query_object(
    "Konferencja w bazie Scopus", "konferencja__baza_scopus"
)


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
