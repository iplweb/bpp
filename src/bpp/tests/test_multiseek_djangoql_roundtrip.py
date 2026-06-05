import pytest
from djangoql.queryset import apply_search

from bpp.djangoql_schema import BppQLSchema
from bpp.models import Rekord

pytestmark = pytest.mark.serial


def _pks_djangoql(frag):
    return set(
        apply_search(Rekord.objects.all(), frag, schema=BppQLSchema)
        .distinct()
        .values_list("pk", flat=True)
    )


@pytest.mark.django_db
def test_roundtrip_jezyk(wydawnictwo_ciagle, denorms):
    from bpp.models import Jezyk

    pol = Jezyk.objects.get_or_create(nazwa="polski", defaults={"skrot": "pol."})[0]
    wydawnictwo_ciagle.jezyk = pol
    wydawnictwo_ciagle.save()
    denorms.flush()

    via_ms = set(Rekord.objects.filter(jezyk=pol).values_list("pk", flat=True))
    via_dql = _pks_djangoql('jezyk.nazwa = "polski"')
    assert via_ms
    assert via_ms == via_dql
