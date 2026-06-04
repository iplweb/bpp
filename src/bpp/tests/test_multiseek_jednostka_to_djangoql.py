import pytest
from djangoql.queryset import apply_search
from model_bakery import baker
from multiseek.logic import DIFFERENT_FEMALE, EQUAL_FEMALE

from bpp.djangoql_schema import BppQLSchema
from bpp.models import Jednostka, Rekord
from bpp.multiseek_registry import registry
from bpp.multiseek_registry.fields.constants import (
    EQUAL_PLUS_SUB_FEMALE,
    EQUAL_PLUS_SUB_UNION_FEMALE,
    UNION_FEMALE,
)

pytestmark = pytest.mark.serial


@pytest.mark.django_db
def test_jednostka_equal_maps_to_autorzy_jednostka_rel():
    j = baker.make(Jednostka, nazwa="Klinika X")
    field = registry.field_by_name["Jednostka"]
    frag = field.to_djangoql(j.pk, str(EQUAL_FEMALE))
    assert frag == f'autorzy.jednostka__rel = "Klinika X [{j.pk}]"'


@pytest.mark.django_db
def test_jednostka_different_maps_to_not_equal():
    j = baker.make(Jednostka, nazwa="Klinika X")
    field = registry.field_by_name["Jednostka"]
    frag = field.to_djangoql(j.pk, str(DIFFERENT_FEMALE))
    assert frag == f'autorzy.jednostka__rel != "Klinika X [{j.pk}]"'


@pytest.mark.django_db
def test_jednostka_plus_subunits_maps_to_virtual_field():
    j = baker.make(Jednostka, nazwa="Klinika X")
    field = registry.field_by_name["Jednostka"]
    frag = field.to_djangoql(j.pk, str(EQUAL_PLUS_SUB_FEMALE))
    assert frag == f'jednostka_z_podjednostkami__rel = "Klinika X [{j.pk}]"'


@pytest.mark.django_db
def test_jednostka_union_is_untranslatable():
    j = baker.make(Jednostka, nazwa="Klinika X")
    field = registry.field_by_name["Jednostka"]
    assert field.to_djangoql(j.pk, str(UNION_FEMALE)) is None


@pytest.mark.django_db
def test_jednostka_plus_subunits_union_is_untranslatable():
    j = baker.make(Jednostka, nazwa="Klinika X")
    field = registry.field_by_name["Jednostka"]
    assert field.to_djangoql(j.pk, str(EQUAL_PLUS_SUB_UNION_FEMALE)) is None


@pytest.mark.django_db
def test_roundtrip_jednostka_plus_subunits_same_rekordy(
    jednostka, jednostka_podrzedna, wydawnictwo_ciagle, autor_jan_kowalski, denorms
):
    """Multiseek Q vs skonwertowane DjangoQL daja ten sam zbior Rekord."""
    # autor w PODRZEDNEJ jednostce; pytamy o NADRZEDNA z '+ podrzedne'
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka_podrzedna)
    denorms.flush()

    field = registry.field_by_name["Jednostka"]
    q = field.real_query(jednostka, EQUAL_PLUS_SUB_FEMALE)
    via_multiseek = set(Rekord.objects.filter(q).values_list("pk", flat=True))

    frag = field.to_djangoql(jednostka.pk, EQUAL_PLUS_SUB_FEMALE)
    via_djangoql = set(
        apply_search(Rekord.objects.all(), frag, schema=BppQLSchema)
        .distinct()
        .values_list("pk", flat=True)
    )
    assert via_multiseek  # niepusty -> test faktycznie cos sprawdza
    assert via_multiseek == via_djangoql
