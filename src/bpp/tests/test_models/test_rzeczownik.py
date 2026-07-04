import pytest
from model_bakery import baker

from bpp.models import Rzeczownik


@pytest.mark.django_db
def test_rzeczownik_str():
    r = baker.make(Rzeczownik, uid="JEDNOSTKA", m="dział")
    assert str(r) == "Rzeczownik JEDNOSTKA = dział"


@pytest.mark.django_db
def test_rzeczownik_mianownik_alias():
    r = baker.make(Rzeczownik, uid="WYDZIAL", m="klinika")
    assert r.mianownik == "klinika"


@pytest.mark.django_db
def test_wiersze_pl_usuniete():
    assert not Rzeczownik.objects.filter(uid__endswith="_PL").exists()
