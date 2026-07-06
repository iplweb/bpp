"""Multi-hosted: pole multiseek „Index Copernicus" respektuje ustawienie
``pokazuj_index_copernicus`` uczelni Z REQUESTU (host), a nie zgaduje
jedynej/pierwszej-z-brzegu.

Bug: bazowy ``BppMultiseekVisibilityMixin.enabled(request)`` wołał
``option_enabled()`` bez argumentów, więc ``IndexCopernicusQueryObject``
nigdy nie dostawał requestu → przy >1 uczelni zawsze ``True`` (widoczne),
niezależnie od ustawienia oglądanej uczelni.
"""

import pytest

from bpp.models import BppUser
from bpp.multiseek_registry.fields.numeric_fields import IndexCopernicusQueryObject
from fixtures.conftest_multisite import make_request_for_site


def _staff_request(site):
    user = BppUser.objects.create_user(
        username=f"ic_staff_{site.pk}", is_staff=True
    )
    return make_request_for_site(site, user=user)


@pytest.mark.django_db
def test_index_copernicus_ukryty_dla_uczelni_z_requestu(
    uczelnia1, uczelnia2, site1, settings
):
    """U1.pokazuj_index_copernicus=False + request na host U1 → pole ukryte,
    mimo że w systemie jest druga uczelnia (get_single_uczelnia_or_none → None
    nie może o tym decydować)."""
    settings.ALLOWED_HOSTS = ["*"]
    uczelnia1.pokazuj_index_copernicus = False
    uczelnia1.save()
    uczelnia2.pokazuj_index_copernicus = True
    uczelnia2.save()

    field = IndexCopernicusQueryObject()
    assert field.enabled(_staff_request(site1)) is False


@pytest.mark.django_db
def test_index_copernicus_widoczny_dla_uczelni_z_requestu(
    uczelnia1, uczelnia2, site2, settings
):
    """U2.pokazuj_index_copernicus=True + request na host U2 → pole widoczne."""
    settings.ALLOWED_HOSTS = ["*"]
    uczelnia1.pokazuj_index_copernicus = False
    uczelnia1.save()
    uczelnia2.pokazuj_index_copernicus = True
    uczelnia2.save()

    field = IndexCopernicusQueryObject()
    assert field.enabled(_staff_request(site2)) is True
