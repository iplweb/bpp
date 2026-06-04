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


def test_scalar_operator_locale_robust():
    from django.utils import translation

    # Build/lookup under English first...
    with translation.override("en"):
        en_key = str(CONTAINS)
        assert scalar_operator_to_djangoql(en_key) == "~"
    # ...then Polish: must still resolve (no frozen-key poisoning).
    with translation.override("pl"):
        pl_key = str(CONTAINS)
        assert scalar_operator_to_djangoql(pl_key) == "~"


def test_render_value_escapes_backslash():
    assert render_value(r"a\b") == r'"a\\b"'
