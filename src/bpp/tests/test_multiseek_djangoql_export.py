from multiseek.logic import (
    CONTAINS,
    DIFFERENT,
    EQUAL,
    GREATER_OR_EQUAL,
    NOT_STARTS_WITH,
)

from bpp.multiseek_registry.djangoql_export import (
    render_value,
    scalar_operator_to_djangoql,
)


def test_render_value_str_quotes_and_escapes():
    assert render_value('on rzekł "tak"') == r'"on rzekł \"tak\""'


def test_render_value_int():
    assert render_value(2024) == "2024"


def test_scalar_operator_mapping():
    assert scalar_operator_to_djangoql(str(EQUAL)) == "="
    assert scalar_operator_to_djangoql(str(DIFFERENT)) == "!="
    assert scalar_operator_to_djangoql(str(CONTAINS)) == "~"
    assert scalar_operator_to_djangoql(str(GREATER_OR_EQUAL)) == ">="
    assert scalar_operator_to_djangoql(str(NOT_STARTS_WITH)) == "not startswith"


def test_scalar_operator_unknown_returns_none():
    assert scalar_operator_to_djangoql("zupełnie nieznany") is None
