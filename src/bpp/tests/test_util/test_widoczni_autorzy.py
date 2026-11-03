"""Wspólna reguła widoczności autora (``pokazuj=False``) — helper
:func:`bpp.util.ukryte_statusy.widoczni_autorzy`."""

import pytest
from django.contrib.auth.models import AnonymousUser, Group
from django.test import RequestFactory
from model_bakery import baker

from bpp.const import GR_WPROWADZANIE_DANYCH
from bpp.models import Autor, Autor_Dyscyplina
from bpp.util.ukryte_statusy import widoczni_autorzy


@pytest.fixture
def autorzy(db):
    return (
        baker.make(Autor, nazwisko="Widoczny", pokazuj=True),
        baker.make(Autor, nazwisko="Ukryty", pokazuj=False),
    )


def _request(user):
    request = RequestFactory().get("/")
    request.user = user
    return request


def _redaktor(django_user_model):
    user = django_user_model.objects.create_user("redaktor")
    grupa, _ = Group.objects.get_or_create(name=GR_WPROWADZANIE_DANYCH)
    user.groups.add(grupa)
    return user


def _zwykly(django_user_model):
    return django_user_model.objects.create_user("zwykly")


@pytest.mark.django_db
def test_widoczni_autorzy_request_none_tylko_widoczni(autorzy):
    widoczny, ukryty = autorzy
    qs = widoczni_autorzy(Autor.objects.filter(pk__in=[widoczny.pk, ukryty.pk]), None)
    assert list(qs) == [widoczny]


@pytest.mark.django_db
def test_widoczni_autorzy_anonim_tylko_widoczni(autorzy):
    widoczny, ukryty = autorzy
    qs = widoczni_autorzy(
        Autor.objects.filter(pk__in=[widoczny.pk, ukryty.pk]),
        _request(AnonymousUser()),
    )
    assert list(qs) == [widoczny]


@pytest.mark.django_db
def test_widoczni_autorzy_zwykly_user_tylko_widoczni(autorzy, django_user_model):
    widoczny, ukryty = autorzy
    qs = widoczni_autorzy(
        Autor.objects.filter(pk__in=[widoczny.pk, ukryty.pk]),
        _request(_zwykly(django_user_model)),
    )
    assert list(qs) == [widoczny]


@pytest.mark.django_db
def test_widoczni_autorzy_redaktor_widzi_wszystkich(autorzy, django_user_model):
    widoczny, ukryty = autorzy
    qs = widoczni_autorzy(
        Autor.objects.filter(pk__in=[widoczny.pk, ukryty.pk]),
        _request(_redaktor(django_user_model)),
    )
    assert set(qs) == {widoczny, ukryty}


@pytest.mark.django_db
def test_widoczni_autorzy_superuser_widzi_wszystkich(autorzy, admin_user):
    widoczny, ukryty = autorzy
    qs = widoczni_autorzy(
        Autor.objects.filter(pk__in=[widoczny.pk, ukryty.pk]), _request(admin_user)
    )
    assert set(qs) == {widoczny, ukryty}


@pytest.mark.django_db
def test_widoczni_autorzy_lookup_model_podrzedny(autorzy, django_user_model):
    widoczny, ukryty = autorzy
    ad_widoczny = baker.make(Autor_Dyscyplina, autor=widoczny, rok=2030)
    ad_ukryty = baker.make(Autor_Dyscyplina, autor=ukryty, rok=2030)
    qs = Autor_Dyscyplina.objects.filter(pk__in=[ad_widoczny.pk, ad_ukryty.pk])

    anonim = widoczni_autorzy(qs, _request(AnonymousUser()), lookup="autor__pokazuj")
    assert list(anonim) == [ad_widoczny]

    redaktor = widoczni_autorzy(
        qs, _request(_redaktor(django_user_model)), lookup="autor__pokazuj"
    )
    assert set(redaktor) == {ad_widoczny, ad_ukryty}
