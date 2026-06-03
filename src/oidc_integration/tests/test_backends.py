"""Testy backendu OIDC (faza 2a — discovery: konto każdemu + zrzut claimów).

``BppOIDCBackend`` jest testowany na instancji utworzonej bez ``__init__``
(``object.__new__``), bo bazowy konstruktor ``mozilla-django-oidc`` wymaga
kompletu ``OIDC_OP_*``/``OIDC_RP_*`` w ustawieniach. Testowane metody
(``verify_claims``, ``create_user``) korzystają tylko ze statycznego
``get_settings``, loggera i ``self.UserModel`` — ustawiamy je ręcznie.
"""

import logging

import pytest
from django.contrib.auth import get_user_model
from django.test import override_settings
from model_bakery import baker

from oidc_integration.backends import BppOIDCBackend


def _backend():
    return object.__new__(BppOIDCBackend)


def test_verify_claims_przepuszcza_gdy_jest_email():
    assert _backend().verify_claims({"email": "jan@uafm.edu.pl"}) is True


def test_verify_claims_odrzuca_bez_emaila():
    # Domyślny scope zawiera "email", więc brak claimu email = odmowa.
    assert _backend().verify_claims({"sub": "123"}) is False


def test_verify_claims_loguje_claimy(caplog):
    with caplog.at_level(logging.INFO, logger="oidc_integration.backends"):
        _backend().verify_claims({"email": "jan@uafm.edu.pl", "sub": "123"})
    assert any("otrzymane claimy" in rec.message for rec in caplog.records)


def test_verify_claims_zrzuca_klucze_na_stderr(capsys):
    _backend().verify_claims(
        {"email": "jan@uafm.edu.pl", "sub": "123", "person_id": "999"}
    )
    err = capsys.readouterr().err
    assert "[OIDC]" in err
    assert "Klucze (3)" in err
    # klucze wypisane alfabetycznie
    assert "email" in err and "person_id" in err and "sub" in err


@pytest.mark.django_db
def test_create_user_zaklada_zwykle_konto_bez_is_staff():
    backend = _backend()
    backend.UserModel = get_user_model()

    user = backend.create_user(
        {
            "preferred_username": "jkowalski",
            "email": "jan@uafm.edu.pl",
            "given_name": "Jan",
            "family_name": "Kowalski",
            "sub": "abc-123",
        }
    )

    assert user.username == "jkowalski"
    assert user.email == "jan@uafm.edu.pl"
    assert user.first_name == "Jan"
    assert user.last_name == "Kowalski"
    assert user.is_staff is False
    assert user.is_superuser is False
    assert user.is_active is True
    # logowanie wyłącznie przez OIDC — brak używalnego hasła lokalnego
    assert not user.has_usable_password()


@pytest.mark.django_db
def test_create_user_unika_kolizji_username():
    UserModel = get_user_model()
    UserModel.objects.create_user(username="jkowalski", email="ktos@inny.pl")

    backend = _backend()
    backend.UserModel = UserModel
    # ten sam preferred_username, inny e-mail → username nie może kolidować
    user = backend.create_user(
        {"preferred_username": "jkowalski", "email": "jan@uafm.edu.pl"}
    )

    assert user.username == "jkowalski-2"


@pytest.mark.django_db
def test_create_user_username_fallback_do_sub():
    backend = _backend()
    backend.UserModel = get_user_model()

    # brak preferred_username i email → username z sub
    user = backend.create_user({"sub": "tylko-sub-789"})

    assert user.username == "tylko-sub-789"
    assert user.email == ""
    assert user.is_staff is False


@pytest.mark.django_db
@override_settings(OIDC_LOGIN_SKROT="UAFM")
def test_create_user_przypisuje_uczelnie_wg_skrotu():
    uczelnia = baker.make("bpp.Uczelnia", skrot="UAFM")
    backend = _backend()
    backend.UserModel = get_user_model()

    user = backend.create_user(
        {"preferred_username": "jkowalski", "email": "jan@uafm.edu.pl"}
    )

    assert list(user.accessible_uczelnie.all()) == [uczelnia]


@pytest.mark.django_db
@override_settings(OIDC_LOGIN_SKROT="UAFM")
def test_create_user_bez_pasujacej_uczelni_nie_przypisuje():
    # Uczelnia o innym skrócie — brak dopasowania, konto bez przypisania.
    baker.make("bpp.Uczelnia", skrot="INNA")
    backend = _backend()
    backend.UserModel = get_user_model()

    user = backend.create_user({"preferred_username": "jkowalski"})

    assert user.accessible_uczelnie.count() == 0


@pytest.mark.django_db
@override_settings(OIDC_LOGIN_SKROT="")
def test_create_user_bez_skrotu_nie_przypisuje():
    baker.make("bpp.Uczelnia", skrot="UAFM")
    backend = _backend()
    backend.UserModel = get_user_model()

    user = backend.create_user({"preferred_username": "jkowalski"})

    assert user.accessible_uczelnie.count() == 0
