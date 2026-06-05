import pytest
from model_bakery import baker
from multiseek.logic import DIFFERENT, EQUAL

from bpp.models import Charakter_Formalny
from bpp.multiseek_registry import registry

pytestmark = pytest.mark.serial


@pytest.mark.django_db
def test_charakter_formalny_maps_to_virtual_field():
    ch = baker.make(Charakter_Formalny, nazwa="Charakter Testowy QL", skrot="QLT")
    Charakter_Formalny.objects.rebuild()
    field = registry.field_by_name["Charakter formalny"]
    frag = field.to_djangoql("Charakter Testowy QL", str(EQUAL))
    assert frag == f'charakter_z_podrzednymi__rel = "Charakter Testowy QL [{ch.pk}]"'


@pytest.mark.django_db
def test_charakter_formalny_strips_indent_prefix():
    ch = baker.make(Charakter_Formalny, nazwa="Charakter Testowy QL", skrot="QLT")
    Charakter_Formalny.objects.rebuild()
    field = registry.field_by_name["Charakter formalny"]
    frag = field.to_djangoql("--- Charakter Testowy QL", str(EQUAL))
    assert frag == f'charakter_z_podrzednymi__rel = "Charakter Testowy QL [{ch.pk}]"'


@pytest.mark.django_db
def test_charakter_formalny_different():
    ch = baker.make(Charakter_Formalny, nazwa="Charakter Testowy QL", skrot="QLT")
    Charakter_Formalny.objects.rebuild()
    field = registry.field_by_name["Charakter formalny"]
    frag = field.to_djangoql("Charakter Testowy QL", str(DIFFERENT))
    assert frag == f'charakter_z_podrzednymi__rel != "Charakter Testowy QL [{ch.pk}]"'


def test_charakter_ogolny_artykul():
    field = registry.field_by_name["Charakter formalny ogólny"]
    assert (
        field.to_djangoql("artykuł", str(EQUAL))
        == 'charakter_formalny.charakter_ogolny = "art"'
    )


def test_charakter_ogolny_ksiazka():
    field = registry.field_by_name["Charakter formalny ogólny"]
    assert (
        field.to_djangoql("książka", str(EQUAL))
        == 'charakter_formalny.charakter_ogolny = "ksi"'
    )


def test_typ_rekordu_publikacje():
    field = registry.field_by_name["Typ rekordu"]
    assert (
        field.to_djangoql("publikacje", str(EQUAL))
        == "charakter_formalny.publikacja = True"
    )


def test_typ_rekordu_inne():
    field = registry.field_by_name["Typ rekordu"]
    assert field.to_djangoql("inne", str(EQUAL)) == (
        "(charakter_formalny.publikacja = False "
        "and charakter_formalny.streszczenie = False)"
    )
