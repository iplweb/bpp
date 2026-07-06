"""Konwersja Multiseek -> DjangoQL dla pól liczbowych.

Multiseek serializuje wartości formularza jako stringi ("5", "0.5",
["2000","2010"]). Renderowane dosłownie trafiałyby w cudzysłów
('impact_factor > "5"'), co DjangoQL odrzuca dla liczbowych pól modelu —
i lić był pomijany jako „nieprzekładalny". Te testy pilnują, że wartości
liczbowe renderują się jako gołe literały i przechodzą walidację schematu.
"""

import pytest
from multiseek.logic import GREATER, GREATER_OR_EQUAL, IN_RANGE, LESSER

from bpp.multiseek_registry import registry
from bpp.multiseek_registry.djangoql_export import leaf_to_djangoql

pytestmark = pytest.mark.serial


def _leaf(field, operator, value):
    return leaf_to_djangoql(
        registry, {"field": field, "operator": str(operator), "value": value}
    )


def test_impact_factor_greater_string_value():
    # Tak jak realny formularz: wartość to string.
    assert _leaf("Impact factor", GREATER, "0") == "impact_factor > 0"


def test_impact_factor_decimal_string_value():
    assert _leaf("Impact factor", GREATER_OR_EQUAL, "2.5") == "impact_factor >= 2.5"


def test_impact_factor_numeric_value_unchanged():
    assert _leaf("Impact factor", GREATER, 0) == "impact_factor > 0"


def test_integer_field_string_value():
    assert _leaf("Liczba cytowań", LESSER, "5") == "liczba_cytowan < 5"


def test_blank_numeric_value_is_untranslatable():
    # Pusta/niepoprawna liczba: multiseek też by nie dopasował -> None.
    assert _leaf("Impact factor", GREATER, "") is None
    assert _leaf("Impact factor", GREATER, "abc") is None


def test_year_range_string_bounds():
    assert (
        _leaf("Zakres lat", IN_RANGE, ["2000", "2010"])
        == "(rok >= 2000 and rok <= 2010)"
    )
