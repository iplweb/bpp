import pytest
from model_bakery import baker
from multiseek.logic import EQUAL

from bpp.multiseek_registry import registry
from bpp.multiseek_registry.djangoql_export import leaf_to_djangoql

pytestmark = pytest.mark.serial


def test_rodzaj_konferencji_krajowa():
    field = registry.field_by_name["Rodzaj konferencji"]
    assert field.to_djangoql("krajowa", str(EQUAL)) == "konferencja.typ_konferencji = 1"


def test_rodzaj_jednostki_normalna():
    # Faza B (#438), III-1: wartości to nazwy słownikowe ``RodzajJednostki``
    # (FK), nie kody starego CharField.
    field = registry.field_by_name["Rodzaj jednostki"]
    assert (
        field.to_djangoql("Standard", str(EQUAL))
        == 'autorzy.jednostka.rodzaj.nazwa = "Standard"'
    )


@pytest.mark.django_db
def test_slowa_kluczowe_maps_to_tag_name():
    field = registry.field_by_name["Słowa kluczowe"]
    assert (
        field.to_djangoql("nowotwór", str(EQUAL)) == 'slowa_kluczowe.name = "nowotwór"'
    )


@pytest.mark.django_db
def test_zewnetrzna_baza_maps_to_nested_rel():
    from bpp.models import Zewnetrzna_Baza_Danych

    z = baker.make(Zewnetrzna_Baza_Danych, nazwa="QL Test Baza")
    frag = leaf_to_djangoql(
        registry,
        {"field": "Zewnętrzna baza danych", "operator": str(EQUAL), "value": z.pk},
    )
    assert frag == f'zewnetrzne_bazy.baza__rel = "QL Test Baza [{z.pk}]"'
