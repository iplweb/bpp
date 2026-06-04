import pytest
from multiseek.logic import (
    AND,
    CONTAINS,
    DIFFERENT,
    EQUAL,
    GREATER_OR_EQUAL,
    NOT_STARTS_WITH,
    OR,
)

from bpp.multiseek_registry import registry
from bpp.multiseek_registry.djangoql_export import (
    leaf_to_djangoql,
    multiseek_form_to_djangoql,
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


@pytest.mark.django_db
def test_leaf_scalar_string_contains():
    frag = leaf_to_djangoql(
        registry,
        {"field": "Tytuł pracy", "operator": str(CONTAINS), "value": "nowotwor"},
    )
    assert frag == 'tytul_oryginalny ~ "nowotwor"'


@pytest.mark.django_db
def test_leaf_year_gte():
    frag = leaf_to_djangoql(
        registry,
        {"field": "Rok", "operator": str(GREATER_OR_EQUAL), "value": 2020},
    )
    assert frag == "rok >= 2020"


@pytest.mark.django_db
def test_leaf_unknown_field_returns_none():
    frag = leaf_to_djangoql(
        registry,
        {"field": "Nie ma takiego pola", "operator": str(CONTAINS), "value": "x"},
    )
    assert frag is None


@pytest.mark.django_db
def test_is_valid_rekord_djangoql_accepts_known_field():
    from bpp.multiseek_registry.djangoql_export import is_valid_rekord_djangoql

    assert is_valid_rekord_djangoql('rok = 2020') is True


@pytest.mark.django_db
def test_is_valid_rekord_djangoql_rejects_unknown_field():
    from bpp.multiseek_registry.djangoql_export import is_valid_rekord_djangoql

    assert is_valid_rekord_djangoql('totalnie_nie_ma_takiego_pola = "x"') is False


@pytest.mark.django_db
def test_two_conditions_and():
    form = {
        "form_data": [
            None,
            {
                "field": "Tytuł pracy",
                "operator": str(CONTAINS),
                "value": "covid",
                "prev_op": None,
            },
            {
                "field": "Rok",
                "operator": str(EQUAL),
                "value": 2023,
                "prev_op": str(AND),
            },
        ],
        "ordering": {},
        "report_type": "0",
    }
    res = multiseek_form_to_djangoql(form, registry)
    assert res.query == 'tytul_oryginalny ~ "covid" and rok = 2023'
    assert res.warnings == []


@pytest.mark.django_db
def test_untranslatable_condition_warns_and_skips():
    form = {
        "form_data": [
            None,
            {
                "field": "Rok",
                "operator": str(EQUAL),
                "value": 2023,
                "prev_op": None,
            },
            {
                "field": "Nie ma pola",
                "operator": str(EQUAL),
                "value": "x",
                "prev_op": str(AND),
            },
        ],
        "ordering": {},
        "report_type": "0",
    }
    res = multiseek_form_to_djangoql(form, registry)
    assert res.query == "rok = 2023"
    assert len(res.warnings) == 1
    assert "Nie ma pola" in res.warnings[0]


@pytest.mark.django_db
def test_empty_form():
    res = multiseek_form_to_djangoql(
        {"form_data": [None], "ordering": {}}, registry
    )
    assert res.query == ""
    assert res.warnings == []


@pytest.mark.django_db
def test_two_conditions_or():
    form = {
        "form_data": [
            None,
            {"field": "Rok", "operator": str(EQUAL), "value": 2020, "prev_op": None},
            {
                "field": "Rok",
                "operator": str(EQUAL),
                "value": 2021,
                "prev_op": str(OR),
            },
        ],
        "ordering": {},
    }
    res = multiseek_form_to_djangoql(form, registry)
    assert res.query == "rok = 2020 or rok = 2021"
    assert res.warnings == []


@pytest.mark.django_db
def test_mixed_or_then_and_is_grouped_left_to_right():
    # Multiseek liczy (A or B) and C; bez nawiasów DjangoQL dałby A or (B and C).
    form = {
        "form_data": [
            None,
            {"field": "Rok", "operator": str(EQUAL), "value": 2020, "prev_op": None},
            {
                "field": "Rok",
                "operator": str(EQUAL),
                "value": 2021,
                "prev_op": str(OR),
            },
            {
                "field": "Rok",
                "operator": str(GREATER_OR_EQUAL),
                "value": 2010,
                "prev_op": str(AND),
            },
        ],
        "ordering": {},
    }
    res = multiseek_form_to_djangoql(form, registry)
    assert res.query == "(rok = 2020 or rok = 2021) and rok >= 2010"
    assert res.warnings == []


@pytest.mark.django_db
def test_pure_and_chain_has_no_parens():
    form = {
        "form_data": [
            None,
            {"field": "Rok", "operator": str(EQUAL), "value": 2020, "prev_op": None},
            {
                "field": "Rok",
                "operator": str(GREATER_OR_EQUAL),
                "value": 2010,
                "prev_op": str(AND),
            },
        ],
        "ordering": {},
    }
    res = multiseek_form_to_djangoql(form, registry)
    assert res.query == "rok = 2020 and rok >= 2010"


@pytest.mark.django_db
def test_nested_subframe_gets_parens():
    form = {
        "form_data": [
            None,
            {"field": "Rok", "operator": str(EQUAL), "value": 2020, "prev_op": None},
            [
                str(AND),
                {
                    "field": "Rok",
                    "operator": str(EQUAL),
                    "value": 2021,
                    "prev_op": None,
                },
                {
                    "field": "Rok",
                    "operator": str(EQUAL),
                    "value": 2022,
                    "prev_op": str(OR),
                },
            ],
        ],
        "ordering": {},
    }
    res = multiseek_form_to_djangoql(form, registry)
    assert res.query == "rok = 2020 and (rok = 2021 or rok = 2022)"


from multiseek.logic import ANDNOT  # noqa: E402


@pytest.mark.django_db
def test_andnot_leaf_inverts_operator():
    form = {"form_data": [
        None,
        {"field": "Rok", "operator": str(EQUAL), "value": 2023, "prev_op": None},
        {"field": "Tytuł pracy", "operator": str(CONTAINS), "value": "abc", "prev_op": str(ANDNOT)},
    ], "ordering": {}}
    res = multiseek_form_to_djangoql(form, registry)
    assert res.query == 'rok = 2023 and tytul_oryginalny !~ "abc"'
    assert res.warnings == []


@pytest.mark.django_db
def test_andnot_value_with_operator_char_is_safe():
    # Wartość zawiera znak '='; inwersja musi działać na operatorze pola,
    # nie na znaku wewnątrz wartości.
    form = {"form_data": [
        None,
        {"field": "Rok", "operator": str(EQUAL), "value": 2023, "prev_op": None},
        {"field": "Tytuł pracy", "operator": str(CONTAINS), "value": "a = b", "prev_op": str(ANDNOT)},
    ], "ordering": {}}
    res = multiseek_form_to_djangoql(form, registry)
    assert res.query == 'rok = 2023 and tytul_oryginalny !~ "a = b"'
    assert res.warnings == []
