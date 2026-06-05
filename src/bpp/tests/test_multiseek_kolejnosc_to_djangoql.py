import pytest
from model_bakery import baker
from multiseek.logic import EQUAL

from bpp.models import Autor
from bpp.multiseek_registry import registry

pytestmark = pytest.mark.serial


@pytest.mark.django_db
def test_pierwsze_nazwisko_is_kolejnosc_zero():
    a = baker.make(Autor, nazwisko="Nowak", imiona="Jan")
    field = registry.field_by_name["Pierwsze nazwisko i imię"]
    frag = field.to_djangoql(a.pk, str(EQUAL))
    assert frag == (
        f'autorzy.autor__rel = "{a} [{a.pk}]" '
        "and autorzy.kolejnosc >= 0 and autorzy.kolejnosc < 1"
    )


@pytest.mark.django_db
def test_ostatnie_nazwisko_best_effort_warns():
    a = baker.make(Autor, nazwisko="Nowak", imiona="Jan")
    field = registry.field_by_name["Ostatnie nazwisko i imię"]
    result = field.to_djangoql(a.pk, str(EQUAL))
    assert isinstance(result, tuple)
    frag, warn = result
    assert frag == f'autorzy.autor__rel = "{a} [{a.pk}]"'
    assert "ostatni" in warn.lower() or "kolejn" in warn.lower()
