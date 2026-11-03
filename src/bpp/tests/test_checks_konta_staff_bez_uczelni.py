import pytest
from django.core import checks
from model_bakery import baker

from bpp.checks import W001_ID, konta_staff_bez_uczelni_check
from bpp.models import BppUser


def _uruchom():
    return konta_staff_bez_uczelni_check(None, databases=["default"])


@pytest.mark.django_db
def test_jedna_uczelnia_brak_ostrzezenia(uczelnia1):
    baker.make(BppUser, username="staff1", is_staff=True, is_active=True)
    assert _uruchom() == []


@pytest.mark.django_db
def test_dwie_uczelnie_staff_bez_przypisania_ostrzezenie(uczelnia1, uczelnia2):
    baker.make(BppUser, username="staff1", is_staff=True, is_active=True)
    wynik = _uruchom()
    assert len(wynik) == 1
    assert isinstance(wynik[0], checks.Warning)
    assert wynik[0].id == W001_ID
    assert "staff1" in wynik[0].msg


@pytest.mark.django_db
def test_przypisany_superuser_nieaktywny_pominieci(uczelnia1, uczelnia2):
    przypisany = baker.make(
        BppUser, username="k_przypisany", is_staff=True, is_active=True
    )
    przypisany.accessible_uczelnie.add(uczelnia1)
    baker.make(
        BppUser,
        username="k_superadmin",
        is_staff=True,
        is_superuser=True,
        is_active=True,
    )
    baker.make(BppUser, username="k_nieaktywny", is_staff=True, is_active=False)
    baker.make(BppUser, username="k_zwykly", is_staff=False, is_active=True)
    baker.make(BppUser, username="k_bezuczelni", is_staff=True, is_active=True)

    wynik = _uruchom()
    assert len(wynik) == 1
    msg = wynik[0].msg
    assert "k_bezuczelni" in msg
    for login in ("k_przypisany", "k_superadmin", "k_nieaktywny", "k_zwykly"):
        assert login not in msg


@pytest.mark.django_db
def test_dwie_uczelnie_wszyscy_przypisani_brak_ostrzezenia(uczelnia1, uczelnia2):
    u = baker.make(BppUser, username="staff1", is_staff=True, is_active=True)
    u.accessible_uczelnie.add(uczelnia1, uczelnia2)
    assert _uruchom() == []


@pytest.mark.django_db
def test_limit_loginow(uczelnia1, uczelnia2):
    for i in range(12):
        baker.make(BppUser, username=f"staff{i:02d}", is_staff=True, is_active=True)
    msg = _uruchom()[0].msg
    assert "12 aktywnych" in msg
    assert "staff09" in msg
    assert "staff10" not in msg
    assert "i 2 innych" in msg


def test_bez_databases_nie_dotyka_bazy():
    # Bez znacznika django_db — dostęp do bazy rzuciłby wyjątek.
    assert konta_staff_bez_uczelni_check(None) == []


@pytest.mark.django_db
def test_zarejestrowany_z_tagiem_database():
    assert konta_staff_bez_uczelni_check in checks.registry.registry.get_checks(
        include_deployment_checks=False
    )
    assert checks.Tags.database in konta_staff_bez_uczelni_check.tags
