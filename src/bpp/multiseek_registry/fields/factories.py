"""Factory functions for creating query objects dynamically."""

from multiseek.logic import (
    EQUALITY_OPS_NONE,
    BooleanQueryObject,
    DecimalQueryObject,
    IntegerQueryObject,
    StringQueryObject,
    ValueListQueryObject,
)

from bpp.multiseek_registry.mixins import BppMultiseekVisibilityMixin


def create_string_query_object(label, field_name, public=True, mixin=None):
    """Factory function to create simple string query objects.

    Args:
        label: Display label for the query object
        field_name: Database field name to query
        public: Whether this field is publicly visible (default True)
        mixin: Optional additional mixin class
    """
    bases = [BppMultiseekVisibilityMixin]
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
        (BppMultiseekVisibilityMixin, DecimalQueryObject),
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
