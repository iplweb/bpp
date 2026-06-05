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


@pytest.mark.django_db
def test_obca_jednostka_inverts_value():
    # "Obca jednostka = True" oznacza skupia_pracownikow = False
    field = registry.field_by_name["Obca jednostka"]
    assert (
        field.to_djangoql(True, str(EQUAL))
        == "autorzy.jednostka.skupia_pracownikow = False"
    )


@pytest.mark.django_db
def test_dyscyplina_ustawiona_true():
    field = registry.field_by_name["Dyscyplina ustawiona"]
    assert field.to_djangoql(True, str(EQUAL)) == "autorzy.dyscyplina_naukowa != None"


@pytest.mark.django_db
def test_dyscyplina_ustawiona_false():
    field = registry.field_by_name["Dyscyplina ustawiona"]
    assert field.to_djangoql(False, str(EQUAL)) == "autorzy.dyscyplina_naukowa = None"


@pytest.mark.django_db
def test_licencja_oa_ustawiona_true():
    field = registry.field_by_name["OpenAccess: licencja ustawiona"]
    assert field.to_djangoql(True, str(EQUAL)) == "openaccess_licencja != None"


@pytest.mark.django_db
def test_strona_www_ustawiona_true():
    field = registry.field_by_name["Strona WWW ustawiona"]
    assert field.to_djangoql(True, str(EQUAL)) == '(www != "" or public_www != "")'
