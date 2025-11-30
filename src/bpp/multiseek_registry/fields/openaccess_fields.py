"""OpenAccess and external data query objects."""

from django.db.models import Q
from multiseek.logic import (
    AUTOCOMPLETE,
    DIFFERENT_ALL,
    DIFFERENT_NONE,
    EQUAL_FEMALE,
    EQUAL_NONE,
    EQUALITY_OPS_ALL,
    EQUALITY_OPS_FEMALE,
    AutocompleteQueryObject,
    UnknownOperation,
)

from bpp.models import (
    Status_Korekty,
    Wydawnictwo_Zwarte,
    Zewnetrzna_Baza_Danych,
    ZewnetrzneBazyDanychView,
)
from bpp.models.konferencja import Konferencja
from bpp.models.openaccess import (
    Czas_Udostepnienia_OpenAccess,
    Licencja_OpenAccess,
    Wersja_Tekstu_OpenAccess,
)
from bpp.models.system import Typ_KBN
from bpp.multiseek_registry.mixins import BppMultiseekVisibilityMixin

from .author_fields import ForeignKeyDescribeMixin
from .factories import create_valuelist_query_object


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


# Simple ValueList query objects created with factory functions
OpenaccessWersjaTekstuQueryObject = create_valuelist_query_object(
    "OpenAccess: wersja tekstu", "openaccess_wersja_tekstu", Wersja_Tekstu_OpenAccess
)
OpenaccessLicencjaQueryObject = create_valuelist_query_object(
    "OpenAccess: licencja", "openaccess_licencja", Licencja_OpenAccess
)
OpenaccessCzasPublikacjiQueryObject = create_valuelist_query_object(
    "OpenAccess: czas udostępnienia",
    "openaccess_czas_publikacji",
    Czas_Udostepnienia_OpenAccess,
)
TypKBNQueryObject = create_valuelist_query_object("Typ MNiSW/MEiN", "typ_kbn", Typ_KBN)
