"""Numeric and scoring query objects."""

from django.conf import settings
from multiseek.logic import (
    EQUALITY_OPS_MALE,
    VALUE_LIST,
    QueryObject,
    RangeQueryObject,
)

from bpp.models import Jezyk, Uczelnia
from bpp.multiseek_registry.mixins import BppMultiseekVisibilityMixin

from .factories import (
    SafeDecimalQueryObject,
    create_decimal_query_object,
    create_integer_query_object,
)


class ZakresLatQueryObject(BppMultiseekVisibilityMixin, RangeQueryObject):
    label = "Zakres lat"
    field_name = "rok"
    bpp_multiseek_visibility_field_name = "zakres_lat"


class JezykQueryObject(BppMultiseekVisibilityMixin, QueryObject):
    label = "Język"
    type = VALUE_LIST
    ops = EQUALITY_OPS_MALE
    values = Jezyk.objects.filter(widoczny=True)
    field_name = "jezyk"

    def value_from_web(self, value):
        return Jezyk.objects.filter(nazwa=value).first()


# Simple integer/decimal query objects created with factory functions
RokQueryObject = create_integer_query_object("Rok", "rok")
ImpactQueryObject = create_decimal_query_object("Impact factor", "impact_factor")
LiczbaCytowanQueryObject = create_integer_query_object(
    "Liczba cytowań", "liczba_cytowan"
)
LiczbaAutorowQueryObject = create_integer_query_object(
    "Liczba autorów", "liczba_autorow"
)


class PunktacjaWewnetrznaEnabledMixin:
    def option_enabled(self, request):
        return settings.UZYWAJ_PUNKTACJI_WEWNETRZNEJ


class PunktacjaWewnetrznaQueryObject(
    BppMultiseekVisibilityMixin, PunktacjaWewnetrznaEnabledMixin, SafeDecimalQueryObject
):
    label = "Punktacja wewnętrzna"
    field_name = "punktacja_wewnetrzna"


# More simple decimal query objects created with factory functions
PunktacjaSNIP = create_decimal_query_object("Punktacja SNIP", "punktacja_snip")
PunktyKBNQueryObject = create_decimal_query_object("Punkty MNiSW/MEiN", "punkty_kbn")


class IndexCopernicusQueryObject(BppMultiseekVisibilityMixin, SafeDecimalQueryObject):
    label = "Index Copernicus"
    field_name = "index_copernicus"

    def option_enabled(self):
        u = Uczelnia.objects.get_default()
        if u is not None:
            return u.pokazuj_index_copernicus
        return True


LiczbaZnakowWydawniczychQueryObject = create_integer_query_object(
    "Liczba znaków wydawniczych", "liczba_znakow_wydawniczych"
)
