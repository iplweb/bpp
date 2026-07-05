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
def test_wydzial_value_from_web_ogranicza_do_korzeni():
    """F4 (#438): ``WydzialQueryObject.value_from_web`` rozwiązuje TYLKO
    jednostki-korzenie (``parent IS NULL``). Stary zapisany search z pk
    nie-roota / dawnego ``Wydzial.pk`` daje GŁOŚNY brak dopasowania (None),
    a nie cichy zły raport na przypadkowej jednostce o kolidującym pk."""
    from bpp.multiseek_registry.fields.unit_fields import WydzialQueryObject

    korzen = baker.make(Jednostka, parent=None)
    dziecko = baker.make(Jednostka, parent=korzen)

    qo = WydzialQueryObject()
    assert qo.value_from_web(korzen.pk) == korzen
    assert qo.value_from_web(dziecko.pk) is None  # nie-korzeń → brak dopasowania
    assert qo.value_from_web(9_999_999) is None  # nieistniejący pk
    assert qo.value_from_web("nie-liczba") is None


@pytest.mark.django_db
def test_wydzial_to_djangoql_ostrzega_o_pominietym_korzeniu():
    """F5 (#438): eksport DjangoQL tłumaczy tylko część poddrzewową i musi
    OSTRZEC, że pomija prace przypięte do samej jednostki-korzenia
    (union ``| autorzy__jednostka=value`` nie ma odpowiednika w DjangoQL)."""
    w = baker.make(Jednostka, nazwa="Wydział Testowy F5", parent=None)
    warnings = []
    frag = leaf_to_djangoql(
        registry,
        {"field": "Wydział", "operator": str(EQUAL), "value": w.pk},
        warnings,
    )
    assert frag == f'autorzy.jednostka.wydzial__rel = "Wydział Testowy F5 [{w.pk}]"'
    assert len(warnings) == 1
    assert "korzenia" in warnings[0]


@pytest.mark.django_db
def test_kierunek_maps_to_nested_rel():
    k = baker.make(Kierunek_Studiow, nazwa="Lekarski")
    frag = leaf_to_djangoql(
        registry, {"field": "Kierunek studiów", "operator": str(EQUAL), "value": k.pk}
    )
    assert frag == f'autorzy.kierunek_studiow__rel = "Lekarski [{k.pk}]"'
