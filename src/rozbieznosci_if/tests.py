import pytest
from model_mommy import mommy

from rozbieznosci_if.models import IgnorujRozbieznoscIf
from rozbieznosci_if.views import RozbieznosciView

from bpp.models import Wydawnictwo_Ciagle, Zrodlo


@pytest.fixture
def wydawnictwo_z_rozbieznoscia(rok):
    zrodlo = mommy.make(Zrodlo)
    zrodlo.punktacja_zrodla_set.create(rok=rok, impact_factor=50)

    wydawnictwo_ciagle = mommy.make(
        Wydawnictwo_Ciagle, impact_factor=10, rok=rok, zrodlo=zrodlo
    )

    return wydawnictwo_ciagle


@pytest.fixture
def wydawnictwo_bez_rozbieznosci(rok):
    zrodlo = mommy.make(Zrodlo)
    zrodlo.punktacja_zrodla_set.create(rok=rok, impact_factor=50)

    wydawnictwo_ciagle = mommy.make(
        Wydawnictwo_Ciagle, rok=rok, impact_factor=50, zrodlo=zrodlo
    )

    return wydawnictwo_ciagle


@pytest.mark.django_db
def test_RozbieznosciView_get_queryset_tak(wydawnictwo_z_rozbieznoscia):
    res = RozbieznosciView().get_queryset()
    assert wydawnictwo_z_rozbieznoscia in res


@pytest.mark.django_db
def test_RozbieznosciView_get_queryset_ignorowane(wydawnictwo_z_rozbieznoscia):
    IgnorujRozbieznoscIf.objects.create(object=wydawnictwo_z_rozbieznoscia)
    res = RozbieznosciView().get_queryset()
    assert wydawnictwo_z_rozbieznoscia not in res


@pytest.mark.django_db
def test_RozbieznosciView_get_queryset_nie(wydawnictwo_bez_rozbieznosci):
    res = RozbieznosciView().get_queryset()
    assert wydawnictwo_bez_rozbieznosci not in res


@pytest.mark.django_db
def test_RozbieznosciView_dodaj_do_ignorowanych(
    wydawnictwo_z_rozbieznoscia, rf, admin_user
):
    req = rf.get("/", data={"_ignore": str(wydawnictwo_z_rozbieznoscia.pk)})
    req.user = admin_user

    rv = RozbieznosciView(kwargs={}, request=req)
    # rv.request = req

    rv.get(req)
    rv.get(req)
    rv.get(req)

    assert IgnorujRozbieznoscIf.objects.count() == 1


@pytest.mark.django_db
def test_RozbieznosciView_ustaw(wydawnictwo_z_rozbieznoscia, rf, admin_user):
    req = rf.get("/", data={"_set": str(wydawnictwo_z_rozbieznoscia.pk)})
    req.user = admin_user

    rv = RozbieznosciView(kwargs={}, request=req)
    # rv.request = req

    rv.get(req)

    wydawnictwo_z_rozbieznoscia.refresh_from_db()
    assert wydawnictwo_z_rozbieznoscia.impact_factor == 50
