import pytest
from djangoql.queryset import apply_search
from model_bakery import baker
from multiseek.logic import DIFFERENT, EQUAL

from bpp.djangoql_schema import BppQLSchema
from bpp.models import Autor, Rekord
from bpp.multiseek_registry import registry

pytestmark = pytest.mark.serial


@pytest.mark.django_db
def test_autor_equal_maps_to_autorzy_autor_rel():
    a = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    field = registry.field_by_name["Nazwisko i imię"]
    frag = field.to_djangoql(a.pk, str(EQUAL))
    assert frag == f'autorzy.autor__rel = "{a} [{a.pk}]"'


@pytest.mark.django_db
def test_autor_different_maps_to_not_equal():
    a = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    field = registry.field_by_name["Nazwisko i imię"]
    frag = field.to_djangoql(a.pk, str(DIFFERENT))
    assert frag == f'autorzy.autor__rel != "{a} [{a.pk}]"'


@pytest.mark.django_db
def test_pierwsze_nazwisko_is_untranslatable():
    a = baker.make(Autor, nazwisko="Kowalski", imiona="Jan")
    field = registry.field_by_name["Pierwsze nazwisko i imię"]
    assert field.to_djangoql(a.pk, str(EQUAL)) is None


@pytest.mark.django_db
def test_roundtrip_autor_equal_same_rekordy(
    autor_jan_kowalski, jednostka, wydawnictwo_ciagle, denorms
):
    wydawnictwo_ciagle.dodaj_autora(autor_jan_kowalski, jednostka)
    denorms.flush()
    field = registry.field_by_name["Nazwisko i imię"]
    q = field.real_query(autor_jan_kowalski, EQUAL)
    via_multiseek = set(Rekord.objects.filter(q).values_list("pk", flat=True))
    frag = field.to_djangoql(autor_jan_kowalski.pk, EQUAL)
    via_djangoql = set(
        apply_search(Rekord.objects.all(), frag, schema=BppQLSchema)
        .distinct()
        .values_list("pk", flat=True)
    )
    assert via_multiseek
    assert via_multiseek == via_djangoql
