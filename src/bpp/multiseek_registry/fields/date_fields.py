"""Date-related query objects."""

from collections.abc import Iterable

from multiseek.logic import DateQueryObject

from bpp.multiseek_registry.mixins import BppMultiseekVisibilityMixin

from .constants import NULL_VALUE


class DataUtworzeniaQueryObject(BppMultiseekVisibilityMixin, DateQueryObject):
    label = "Data utworzenia"
    field_name = "utworzono"
    public = False

    def value_for_description(self, value):
        value = self.value_from_web(value)
        if value is None:
            return NULL_VALUE
        if isinstance(value, Iterable):
            return f"od {value[0]} do {value[1]}"
        return str(value)


class OstatnioZmieniony(DataUtworzeniaQueryObject):
    label = "Ostatnio zmieniony"
    field_name = "ostatnio_zmieniony"
    public = False
