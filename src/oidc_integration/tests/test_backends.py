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


def test_verify_claims_przepuszcza_znormalizowane_claimy_z_mail():
    # Keycloak realmu KA wystawia `mail`; po normalizacji (get_userinfo)
    # claimy mają `email` i weryfikacja przechodzi.
    backend = _backend()
    claims = backend._normalized({"mail": "jan@uafm.edu.pl", "sub": "123"})
    assert backend.verify_claims(claims) is True


def test_verify_claims_loguje_klucze_na_debug(caplog):
    with caplog.at_level(logging.DEBUG, logger="oidc_integration.backends"):
        _backend().verify_claims(
            {"email": "jan@uafm.edu.pl", "sub": "123", "person_id": "999"}
        )
    debug = [r for r in caplog.records if r.levelno == logging.DEBUG]
    joined = " ".join(r.getMessage() for r in debug)
    assert "email" in joined and "person_id" in joined and "sub" in joined


def test_verify_claims_nie_pisze_bannera_na_stderr(capsys):
    _backend().verify_claims({"email": "jan@uafm.edu.pl", "sub": "123"})
    assert "[OIDC]" not in capsys.readouterr().err


def test_normalized_uzupelnia_email_z_mail():
    out = _backend()._normalized({"mail": "jan@uafm.edu.pl", "sub": "1"})
    assert out["email"] == "jan@uafm.edu.pl"
    # oryginalny `mail` zachowany
    assert out["mail"] == "jan@uafm.edu.pl"


def test_normalized_nie_nadpisuje_istniejacego_email():
    out = _backend()._normalized(
        {"email": "wlasny@uafm.edu.pl", "mail": "inny@uafm.edu.pl"}
    )
    assert out["email"] == "wlasny@uafm.edu.pl"


def test_normalized_bez_mail_nie_dorabia_email():
    out = _backend()._normalized({"sub": "123"})
    assert "email" not in out


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
def test_create_user_email_z_mail_po_normalizacji():
    # Pełna ścieżka: claimy z Keycloaka (`mail`, `preferred_username`) →
    # normalizacja → create_user. Konto dostaje username z preferred_username
    # i e-mail z mail.
    backend = _backend()
    backend.UserModel = get_user_model()

    user = backend.create_user(
        backend._normalized(
            {
                "preferred_username": "99999@student-afm.edu.pl",
                "mail": "99999@student-afm.edu.pl",
                "given_name": "Test",
                "family_name": "Testowy",
                "sub": "66662961",
            }
        )
    )

    assert user.username == "99999@student-afm.edu.pl"
    assert user.email == "99999@student-afm.edu.pl"
    assert user.first_name == "Test"
    assert user.last_name == "Testowy"
    assert user.is_staff is False


def test_get_userinfo_normalizuje_mail_na_email(mocker):
    backend = _backend()
    mocker.patch.object(
        BppOIDCBackend.__bases__[0],
        "get_userinfo",
        return_value={"mail": "jan@uafm.edu.pl", "sub": "1"},
    )
    out = backend.get_userinfo("acc", "id", {"payload": True})
    assert out["email"] == "jan@uafm.edu.pl"


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
