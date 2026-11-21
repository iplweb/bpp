"""Factory functions for creating query objects dynamically."""

from django.db.models import Q
from multiseek.logic import (
    DIFFERENT_ALL,
    EQUALITY_OPS_ALL,
    EQUALITY_OPS_NONE,
    BooleanQueryObject,
    DecimalQueryObject,
    IntegerQueryObject,
    StringQueryObject,
    ValueListQueryObject,
)

from bpp.multiseek_registry.mixins import BppMultiseekVisibilityMixin


class SafeDecimalQueryObject(DecimalQueryObject):
    """DecimalQueryObject that rejects NaN and Infinity values.

    Decimal('NaN') and Decimal('Infinity') are valid Python Decimal objects,
    but Django's DecimalField rejects them during filtering, causing ValidationError.
    """

    def value_from_web(self, value):
        result = super().value_from_web(value)
        if result is not None and (result.is_nan() or result.is_infinite()):
            return None
        return result


class PustyNapisLubNullMixin:
    """Warunek „równe (puste)” łapie także rekordy z NULL w polu tekstowym.

    Bez tego multiseek buduje ``Q(pole="")``, a w bazie brak wartości to
    zwykle NULL — wyszukiwanie prac bez DOI zwracało pustą listę.
    „Różne (puste)” odwrotnie: wyklucza zarówno NULL, jak i pusty napis.
    """

    def _pusta_rownosc(self, value, operation):
        """True dla „równe”/„różne” z pustą wartością; False dla reszty."""
        if value not in (None, ""):
            return False
        return str(operation) in [str(x) for x in EQUALITY_OPS_ALL]

    def _czy_rozne(self, operation):
        return str(operation) in [str(x) for x in DIFFERENT_ALL]

    def real_query(self, value, operation):
        if not self._pusta_rownosc(value, operation):
            return super().real_query(value, operation)
        ret = Q(**{f"{self.field_name}__isnull": True}) | Q(**{self.field_name: ""})
        return ~ret if self._czy_rozne(operation) else ret

    def to_djangoql(self, value, operation):
        """Odpowiednik ``real_query`` dla eksportu do DjangoQL."""
        from bpp.multiseek_registry.djangoql_export import (
            _default_leaf,
            _orm_name,
            _orm_path_to_djangoql,
        )

        if not self._pusta_rownosc(value, operation):
            return _default_leaf(self, value, operation)
        sciezka = _orm_path_to_djangoql(_orm_name(self))
        if self._czy_rozne(operation):
            return f'({sciezka} != None and {sciezka} != "")'
        return f'({sciezka} = None or {sciezka} = "")'


def create_string_query_object(label, field_name, public=True, mixin=None):
    """Factory function to create simple string query objects.

    Args:
        label: Display label for the query object
        field_name: Database field name to query
        public: Whether this field is publicly visible (default True)
        mixin: Optional additional mixin class
    """
    bases = [BppMultiseekVisibilityMixin, PustyNapisLubNullMixin]
    if mixin:
        bases.append(mixin)
    bases.append(StringQueryObject)

    return type(
        f"{field_name.title().replace('_', '')}QueryObject",
        tuple(bases),
        {"label": label, "field_name": field_name, "public": public},
    )


def create_boolean_query_object(label, field_name, ops=None, public=True):
    """Factory function to create simple boolean query objects.

    Args:
        label: Display label for the query object
        field_name: Database field name to query
        ops: Operations list (default EQUALITY_OPS_NONE)
        public: Whether this field is publicly visible (default True)
    """
    if ops is None:
        ops = EQUALITY_OPS_NONE

    return type(
        f"{field_name.title().replace('_', '').replace('.', '')}QueryObject",
        (BppMultiseekVisibilityMixin, BooleanQueryObject),
        {"label": label, "field_name": field_name, "ops": ops, "public": public},
    )


def create_integer_query_object(label, field_name, public=True):
    """Factory function to create simple integer query objects.

    Args:
        label: Display label for the query object
        field_name: Database field name to query
        public: Whether this field is publicly visible (default True)
    """
    return type(
        f"{field_name.title().replace('_', '')}QueryObject",
        (BppMultiseekVisibilityMixin, IntegerQueryObject),
        {"label": label, "field_name": field_name, "public": public},
    )


def create_decimal_query_object(label, field_name, public=True):
    """Factory function to create simple decimal query objects.

    Args:
        label: Display label for the query object
        field_name: Database field name to query
        public: Whether this field is publicly visible (default True)
    """
    return type(
        f"{field_name.title().replace('_', '')}QueryObject",
        (BppMultiseekVisibilityMixin, SafeDecimalQueryObject),
        {"label": label, "field_name": field_name, "public": public},
    )


def create_valuelist_query_object(
    label, field_name, model, name_field="nazwa", ops=None
):
    """Factory function to create ValueList query objects with model lookup.

    Args:
        label: Display label for the query object
        field_name: Database field name to query
        model: Django model class for values
        name_field: Field name to use for value lookup (default 'nazwa')
        ops: Operations list (default None, uses ValueListQueryObject default)
    """
    class_attrs = {
        "label": label,
        "field_name": field_name,
        "values": model.objects.all(),
        # Konwersja Multiseek -> DjangoQL: value-list jako string po polu-nazwie.
        "djangoql_value_field": name_field,
    }
    if ops:
        class_attrs["ops"] = ops

    def value_from_web(self, value):
        return model.objects.get(**{name_field: value})

    class_attrs["value_from_web"] = value_from_web

    return type(
        f"{field_name.title().replace('_', '')}QueryObject",
        (BppMultiseekVisibilityMixin, ValueListQueryObject),
        class_attrs,
    )
