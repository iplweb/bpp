import pytest
from djangoql.queryset import apply_search
from model_bakery import baker

from bpp.djangoql_schema import BppQLSchema
from bpp.models import Charakter_Formalny, Rekord

pytestmark = pytest.mark.serial


@pytest.mark.django_db
def test_charakter_z_podrzednymi_field_present_on_rekord():
    s = BppQLSchema(Rekord)
    fields = s.get_fields(Rekord)
    assert "charakter_z_podrzednymi__rel" in fields


@pytest.mark.django_db
def test_charakter_z_podrzednymi_matches_descendants(wydawnictwo_ciagle, denorms):
    parent = baker.make(Charakter_Formalny, nazwa="Artykuły", skrot="ART")
    child = baker.make(
        Charakter_Formalny, nazwa="Artykuł oryginalny", skrot="AO", parent=parent
    )
    Charakter_Formalny.objects.rebuild()
    wydawnictwo_ciagle.charakter_formalny = child
    wydawnictwo_ciagle.save()
    denorms.flush()

    frag = f'charakter_z_podrzednymi__rel = "Artykuły [{parent.pk}]"'
    pks = set(
        apply_search(Rekord.objects.all(), frag, schema=BppQLSchema)
        .distinct()
        .values_list("pk", flat=True)
    )
    assert Rekord.objects.get_for_model(wydawnictwo_ciagle).pk in pks
