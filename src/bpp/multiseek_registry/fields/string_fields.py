"""String-based query objects for text searching."""

from django.contrib.postgres.search import SearchQuery
from django.db.models import Q
from django.db.models.expressions import F
from multiseek import logic
from multiseek.logic import (
    DIFFERENT_NONE,
    EQUAL_NONE,
    EQUALITY_OPS_NONE,
    AutocompleteQueryObject,
    StringQueryObject,
    UnknownOperation,
)

from bpp.models import Zrodlo
from bpp.multiseek_registry.mixins import BppMultiseekVisibilityMixin

from .factories import create_string_query_object


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


# Simple string query objects created with factory function
AdnotacjeQueryObject = create_string_query_object(
    "Adnotacje", "adnotacje", public=False
)
DOIQueryObject = create_string_query_object("DOI", "doi", public=False)
InformacjeQueryObject = create_string_query_object("Informacje", "informacje")
SzczegolyQueryObject = create_string_query_object("Szczegóły", "szczegoly")
UwagiQueryObject = create_string_query_object("Uwagi", "uwagi")


class ORCIDQueryObject(BppMultiseekVisibilityMixin, StringQueryObject):
    label = "ORCID"
    ops = [EQUAL_NONE, DIFFERENT_NONE]
    field_name = "autorzy__autor__orcid"


class ZrodloQueryObject(BppMultiseekVisibilityMixin, AutocompleteQueryObject):
    label = "Źródło"
    ops = EQUALITY_OPS_NONE
    model = Zrodlo
    field_name = "zrodlo"
    url = "bpp:zrodlo-autocomplete"
