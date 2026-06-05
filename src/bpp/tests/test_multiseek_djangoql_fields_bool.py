import pytest
from multiseek.logic import EQUAL

from bpp.multiseek_registry import registry
from bpp.multiseek_registry.djangoql_export import leaf_to_djangoql

pytestmark = pytest.mark.serial


@pytest.mark.django_db
def test_afiliuje_true():
    frag = leaf_to_djangoql(
        registry, {"field": "Afiliuje", "operator": str(EQUAL), "value": True}
    )
    assert frag == "autorzy.afiliuje = True"


@pytest.mark.django_db
def test_oswiadczenie_ken_false():
    frag = leaf_to_djangoql(
        registry,
        {"field": "Oświadczenie KEN", "operator": str(EQUAL), "value": False},
    )
    assert frag == "autorzy.oswiadczenie_ken = False"
