import pytest
from django.contrib.auth.models import AnonymousUser, Group
from django.test import RequestFactory
from model_bakery import baker

from bpp.models import Uczelnia
from nowe_raporty.models import DefinicjaRaportu


def _request(user, uczelnia=None):
    req = RequestFactory().get("/")
    req.user = user
    if uczelnia is not None:
        # get_for_request() zwraca request._uczelnia jesli ustawione
        req._uczelnia = uczelnia
    return req


@pytest.fixture
def anon():
    return AnonymousUser()


@pytest.fixture
def zwykly(django_user_model):
    return baker.make(django_user_model, is_staff=False, is_superuser=False)


@pytest.fixture
def staff(django_user_model):
    return baker.make(django_user_model, is_staff=True, is_superuser=False)


@pytest.fixture
def superuser(django_user_model):
    return baker.make(django_user_model, is_staff=True, is_superuser=True)


# --- aktywny ---------------------------------------------------------------


@pytest.mark.django_db
def test_nieaktywny_ukryty_takze_dla_superusera(superuser):
    d = baker.make(
        DefinicjaRaportu,
        aktywny=False,
        poziom_dostepu=DefinicjaRaportu.DOSTEP_WSZYSCY,
    )
    assert d.widoczny_dla(_request(superuser)) is False


# --- poziom dostepu --------------------------------------------------------


@pytest.mark.django_db
def test_wszyscy_widoczny_dla_anonima(anon):
    d = baker.make(
        DefinicjaRaportu, aktywny=True, poziom_dostepu=DefinicjaRaportu.DOSTEP_WSZYSCY
    )
    assert d.widoczny_dla(_request(anon)) is True


@pytest.mark.django_db
def test_zalogowani_ukryty_dla_anonima_widoczny_dla_zalogowanego(anon, zwykly):
    d = baker.make(
        DefinicjaRaportu,
        aktywny=True,
        poziom_dostepu=DefinicjaRaportu.DOSTEP_ZALOGOWANI,
    )
    assert d.widoczny_dla(_request(anon)) is False
    assert d.widoczny_dla(_request(zwykly)) is True


@pytest.mark.django_db
def test_staff_widoczny_tylko_dla_staff(zwykly, staff):
    d = baker.make(
        DefinicjaRaportu, aktywny=True, poziom_dostepu=DefinicjaRaportu.DOSTEP_STAFF
    )
    assert d.widoczny_dla(_request(zwykly)) is False
    assert d.widoczny_dla(_request(staff)) is True


@pytest.mark.django_db
def test_superuser_poziom_widoczny_tylko_dla_superusera(staff, superuser):
    d = baker.make(
        DefinicjaRaportu,
        aktywny=True,
        poziom_dostepu=DefinicjaRaportu.DOSTEP_SUPERUSER,
    )
    assert d.widoczny_dla(_request(staff)) is False
    assert d.widoczny_dla(_request(superuser)) is True


# --- grupy (AND, OR wewnatrz) ----------------------------------------------


@pytest.mark.django_db
def test_wymagana_grupa_blokuje_bez_czlonkostwa(zwykly):
    d = baker.make(
        DefinicjaRaportu,
        aktywny=True,
        poziom_dostepu=DefinicjaRaportu.DOSTEP_ZALOGOWANI,
    )
    g = Group.objects.create(name="raporty-x")
    d.wymagane_grupy.add(g)
    assert d.widoczny_dla(_request(zwykly)) is False
    zwykly.groups.add(g)
    assert d.widoczny_dla(_request(zwykly)) is True


@pytest.mark.django_db
def test_wymagane_grupy_or_wewnatrz(zwykly):
    d = baker.make(
        DefinicjaRaportu,
        aktywny=True,
        poziom_dostepu=DefinicjaRaportu.DOSTEP_ZALOGOWANI,
    )
    g1 = Group.objects.create(name="g1")
    g2 = Group.objects.create(name="g2")
    d.wymagane_grupy.add(g1, g2)
    zwykly.groups.add(g2)  # member jednej z dwoch wystarczy
    assert d.widoczny_dla(_request(zwykly)) is True


@pytest.mark.django_db
def test_superuser_pomija_poziom_i_grupy(superuser):
    d = baker.make(
        DefinicjaRaportu,
        aktywny=True,
        poziom_dostepu=DefinicjaRaportu.DOSTEP_ZALOGOWANI,
    )
    d.wymagane_grupy.add(Group.objects.create(name="g"))
    # superuser nie jest w grupie, a i tak widzi
    assert d.widoczny_dla(_request(superuser)) is True


# --- M2M uczelnie (puste = wszedzie) ---------------------------------------


@pytest.mark.django_db
def test_uczelnie_puste_widoczny_wszedzie(zwykly):
    uczelnia = baker.make(Uczelnia)
    d = baker.make(
        DefinicjaRaportu, aktywny=True, poziom_dostepu=DefinicjaRaportu.DOSTEP_WSZYSCY
    )
    assert d.widoczny_dla(_request(zwykly, uczelnia=uczelnia)) is True


@pytest.mark.django_db
def test_uczelnie_ustawione_tylko_na_swojej(zwykly):
    a = baker.make(Uczelnia)
    b = baker.make(Uczelnia)
    d = baker.make(
        DefinicjaRaportu, aktywny=True, poziom_dostepu=DefinicjaRaportu.DOSTEP_WSZYSCY
    )
    d.uczelnie.add(a)
    assert d.widoczny_dla(_request(zwykly, uczelnia=a)) is True
    assert d.widoczny_dla(_request(zwykly, uczelnia=b)) is False


@pytest.mark.django_db
def test_uczelnie_filtr_dotyczy_takze_superusera(superuser):
    a = baker.make(Uczelnia)
    b = baker.make(Uczelnia)
    d = baker.make(
        DefinicjaRaportu, aktywny=True, poziom_dostepu=DefinicjaRaportu.DOSTEP_WSZYSCY
    )
    d.uczelnie.add(a)
    # raport przypisany do uczelni A nie pokazuje sie na stronach uczelni B
    assert d.widoczny_dla(_request(superuser, uczelnia=b)) is False
