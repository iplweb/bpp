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


import pytest  # noqa: E402
from model_bakery import baker  # noqa: E402

from bpp.multiseek_registry import registry  # noqa: E402
from bpp.multiseek_registry.djangoql_export import leaf_to_djangoql  # noqa: E402


@pytest.mark.django_db
@pytest.mark.serial
def test_jezyk_maps_to_nazwa():
    frag = leaf_to_djangoql(
        registry, {"field": "Język", "operator": str(EQUAL), "value": "polski"}
    )
    assert frag == 'jezyk.nazwa = "polski"'


@pytest.mark.django_db
@pytest.mark.serial
def test_typ_kbn_maps_to_nazwa():
    from bpp.models.system import Typ_KBN

    baker.make(Typ_KBN, nazwa="PO")
    frag = leaf_to_djangoql(
        registry, {"field": "Typ MNiSW/MEiN", "operator": str(EQUAL), "value": "PO"}
    )
    assert frag == 'typ_kbn.nazwa = "PO"'


@pytest.mark.django_db
@pytest.mark.serial
def test_typ_odpowiedzialnosci_maps_to_nested_nazwa():
    frag = leaf_to_djangoql(
        registry,
        {"field": "Typ odpowiedzialności", "operator": str(EQUAL), "value": "autor"},
    )
    assert frag == 'autorzy.typ_odpowiedzialnosci.nazwa = "autor"'
