"""Widoczność nagród w ``/api/v1/nagroda/`` zależna od obiektu, do którego
nagroda jest przypięta (status korekty, ``nie_eksportuj_przez_api``,
``Autor.pokazuj``)."""

import pytest
from django.contrib.auth.models import Group
from django.urls import reverse
from model_bakery import baker
from rest_framework.test import APIClient

from bpp.const import GR_WPROWADZANIE_DANYCH


def _klient(user=None):
    c = APIClient()
    if user is not None:
        c.force_authenticate(user=user)
    return c


def _anonim():
    return _klient()


def _zwykly_zalogowany():
    return _klient(baker.make("bpp.BppUser", is_staff=False, is_superuser=False))


def _redaktor():
    u = baker.make("bpp.BppUser", is_staff=False, is_superuser=False)
    grupa, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    u.groups.add(grupa)
    return _klient(u)


def _superuser():
    return _klient(baker.make("bpp.BppUser", is_staff=True, is_superuser=True))


BEZ_UPRAWNIEN = [
    pytest.param(_anonim, id="anonim"),
    pytest.param(_zwykly_zalogowany, id="zwykly_zalogowany"),
]
Z_UPRAWNIENIAMI = [
    pytest.param(_redaktor, id="redaktor"),
    pytest.param(_superuser, id="superuser"),
]


def _ukryty_status(uczelnia, przed_korekta):
    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)
    return baker.make("bpp.Wydawnictwo_Ciagle", status_korekty=przed_korekta)


def _nie_eksportowany(uczelnia, przed_korekta):
    return baker.make("bpp.Wydawnictwo_Zwarte", nie_eksportuj_przez_api=True)


def _ukryty_autor(uczelnia, przed_korekta):
    return baker.make("bpp.Autor", pokazuj=False)


UKRYTE_OBIEKTY = [
    pytest.param(_ukryty_status, id="ukryty_status"),
    pytest.param(_nie_eksportowany, id="nie_eksportuj_przez_api"),
    pytest.param(_ukryty_autor, id="autor_pokazuj_false"),
]


def _ids_listy(klient):
    res = klient.get(reverse("api_v1:nagroda-list"))
    assert res.status_code == 200
    return {wiersz["id"] for wiersz in res.json()["results"]}


def _detal(klient, nagroda):
    return klient.get(reverse("api_v1:nagroda-detail", args=(nagroda.pk,)))


@pytest.fixture
def zwykla_nagroda(db):
    return baker.make("bpp.Nagroda", object=baker.make("bpp.Wydawnictwo_Zwarte"))


@pytest.mark.django_db
@pytest.mark.parametrize("obiekt", UKRYTE_OBIEKTY)
@pytest.mark.parametrize("fabryka", BEZ_UPRAWNIEN)
def test_nagroda_ukrytego_obiektu_niewidoczna(
    fabryka, obiekt, uczelnia, przed_korekta, zwykla_nagroda
):
    ukryta = baker.make("bpp.Nagroda", object=obiekt(uczelnia, przed_korekta))
    klient = fabryka()

    assert _ids_listy(klient) == {zwykla_nagroda.pk}
    assert _detal(klient, ukryta).status_code == 404
    assert _detal(klient, zwykla_nagroda).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("obiekt", UKRYTE_OBIEKTY)
@pytest.mark.parametrize("fabryka", Z_UPRAWNIENIAMI)
def test_nagroda_ukrytego_obiektu_widoczna_dla_uprawnionych(
    fabryka, obiekt, uczelnia, przed_korekta, zwykla_nagroda
):
    ukryta = baker.make("bpp.Nagroda", object=obiekt(uczelnia, przed_korekta))
    klient = fabryka()

    assert _ids_listy(klient) == {zwykla_nagroda.pk, ukryta.pk}
    assert _detal(klient, ukryta).status_code == 200


@pytest.mark.django_db
@pytest.mark.parametrize("fabryka", BEZ_UPRAWNIEN + Z_UPRAWNIENIAMI)
def test_nagrody_widocznych_obiektow_dla_wszystkich(
    fabryka, uczelnia, przed_korekta, po_korekcie
):
    uczelnia.ukryj_status_korekty_set.create(status_korekty=przed_korekta)
    nagrody = {
        baker.make("bpp.Nagroda", object=obj).pk
        for obj in (
            baker.make("bpp.Wydawnictwo_Ciagle", status_korekty=po_korekcie),
            baker.make("bpp.Wydawnictwo_Zwarte", nie_eksportuj_przez_api=False),
            baker.make("bpp.Autor", pokazuj=True),
        )
    }

    assert _ids_listy(fabryka()) == nagrody
