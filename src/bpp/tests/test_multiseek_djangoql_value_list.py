from multiseek.logic import DIFFERENT, EQUAL

from bpp.multiseek_registry.djangoql_export import _value_list_leaf
from bpp.multiseek_registry.fields.constants import UNION


class _VL:
    field_name = "jezyk"
    djangoql_value_field = "nazwa"


def test_value_list_equal():
    assert _value_list_leaf(_VL(), "polski", str(EQUAL)) == 'jezyk.nazwa = "polski"'


def test_value_list_different():
    assert _value_list_leaf(_VL(), "polski", str(DIFFERENT)) == 'jezyk.nazwa != "polski"'


def test_value_list_empty_value():
    assert _value_list_leaf(_VL(), "", str(EQUAL)) == 'jezyk.nazwa = ""'


def test_value_list_union_warns():
    frag, warn = _value_list_leaf(_VL(), "polski", str(UNION))
    assert frag == 'jezyk.nazwa = "polski"'
    assert "wspóln" in warn.lower()


def test_value_list_respects_djangoql_field_name():
    class VL2:
        field_name = "typ_odpowiedzialnosci"
        djangoql_field_name = "autorzy__typ_odpowiedzialnosci"
        djangoql_value_field = "nazwa"

    assert (
        _value_list_leaf(VL2(), "autor", str(EQUAL))
        == 'autorzy.typ_odpowiedzialnosci.nazwa = "autor"'
    )
