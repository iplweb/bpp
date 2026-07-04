import pytest
from model_bakery import baker
from multiseek.logic import EQUAL

from bpp.models import Kierunek_Studiow
from bpp.models.struktura import Jednostka
from bpp.multiseek_registry import registry
from bpp.multiseek_registry.djangoql_export import leaf_to_djangoql

pytestmark = pytest.mark.serial


@pytest.mark.django_db
def test_wydzial_maps_to_nested_rel():
    # Faza B (#438): „wydział" w multiseeku to jednostka top-level (picker
    # Jednostka), więc wartość rozwiązuje się jako Jednostka-korzeń.
    w = baker.make(Jednostka, nazwa="Wydział Lekarski", parent=None)
    frag = leaf_to_djangoql(
        registry, {"field": "Wydział", "operator": str(EQUAL), "value": w.pk}
    )
    assert frag == f'autorzy.jednostka.wydzial__rel = "Wydział Lekarski [{w.pk}]"'


@pytest.mark.django_db
def test_kierunek_maps_to_nested_rel():
    k = baker.make(Kierunek_Studiow, nazwa="Lekarski")
    frag = leaf_to_djangoql(
        registry, {"field": "Kierunek studiów", "operator": str(EQUAL), "value": k.pk}
    )
    assert frag == f'autorzy.kierunek_studiow__rel = "Lekarski [{k.pk}]"'
