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


def test_normalized_mail_wygrywa_z_email():
    # Default mail-first: `mail` (instytucjonalny) ma pierwszeństwo nad `email`
    # (prywatny). UAFM: email='...@kowalczewski.pl', mail='...@uafm.edu.pl'.
    out = _backend()._normalized(
        {"email": "prywatny@kowalczewski.pl", "mail": "instytut@uafm.edu.pl"}
    )
    assert out["email"] == "instytut@uafm.edu.pl"
    # oryginalny prywatny `email` zachowany pod swoim kluczem
    assert out["mail"] == "instytut@uafm.edu.pl"


def test_normalized_email_jako_fallback_gdy_brak_mail():
    # `email` używany tylko, gdy brak `mail`.
    out = _backend()._normalized({"email": "prywatny@kowalczewski.pl", "sub": "1"})
    assert out["email"] == "prywatny@kowalczewski.pl"


@override_settings(OIDC_EMAIL_CLAIMS=["email", "mail"])
def test_normalized_kolejnosc_emaila_konfigurowalna():
    # Override przez settings: gdy realm woli `email`, można przestawić.
    out = _backend()._normalized(
        {"email": "wlasny@uafm.edu.pl", "mail": "inny@uafm.edu.pl"}
    )
    assert out["email"] == "wlasny@uafm.edu.pl"


def test_normalized_uzupelnia_email_z_e_mail_z_myslnikiem():
    out = _backend()._normalized({"e-mail": "jan@uafm.edu.pl", "sub": "1"})
    assert out["email"] == "jan@uafm.edu.pl"


def test_normalized_uzupelnia_email_z_e_mail_z_podkresleniem():
    out = _backend()._normalized({"e_mail": "jan@uafm.edu.pl", "sub": "1"})
    assert out["email"] == "jan@uafm.edu.pl"


def test_normalized_priorytet_mail_przed_wszystkimi():
    # Default mail-first: `mail` wygrywa ze wszystkimi wariantami.
    out = _backend()._normalized(
        {
            "email": "a@uafm.edu.pl",
            "e-mail": "b@uafm.edu.pl",
            "e_mail": "c@uafm.edu.pl",
            "mail": "d@uafm.edu.pl",
        }
    )
    assert out["email"] == "d@uafm.edu.pl"


def test_normalized_priorytet_email_przed_e_mail_gdy_brak_mail():
    # brak `mail`; dalsza kolejność: email → e-mail → e_mail.
    out = _backend()._normalized({"email": "a@uafm.edu.pl", "e-mail": "b@uafm.edu.pl"})
    assert out["email"] == "a@uafm.edu.pl"


def test_normalized_fallback_na_preferred_username_z_domena():
    # brak claimów e-mail; preferred_username wygląda jak adres → użyj go
    out = _backend()._normalized(
        {"preferred_username": "99999@student-afm.edu.pl", "sub": "1"}
    )
    assert out["email"] == "99999@student-afm.edu.pl"


def test_normalized_odrzuca_gdy_username_bez_domeny():
    # brak claimów e-mail, a preferred_username bez domeny → odrzuć logowanie
    from django.core.exceptions import SuspiciousOperation

    with pytest.raises(SuspiciousOperation):
        _backend()._normalized({"preferred_username": "jkowalski", "sub": "1"})


def test_normalized_odrzuca_gdy_brak_email_i_username():
    from django.core.exceptions import SuspiciousOperation

    with pytest.raises(SuspiciousOperation):
        _backend()._normalized({"sub": "123"})


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
@override_settings(OIDC_USERNAME_CLAIMS=["email", "sub"])
def test_create_user_username_z_settingu():
    # Override źródła username: gdy konfiguracja woli email zamiast
    # preferred_username, konto bierze username z email.
    backend = _backend()
    backend.UserModel = get_user_model()

    user = backend.create_user(
        {
            "preferred_username": "jkowalski",
            "email": "jan@uafm.edu.pl",
            "sub": "abc-123",
        }
    )

    assert user.username == "jan@uafm.edu.pl"


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
@override_settings(OIDC_LOGIN_SKROT="UAFM")
def test_create_user_dopasowuje_autora_w_uczelni():
    # Po przypisaniu uczelni (skrot UAFM) konto dopasowuje autora z tej
    # uczelni po e-mailu (= znormalizowany `mail`).
    uczelnia = baker.make("bpp.Uczelnia", skrot="UAFM")
    jednostka = baker.make("bpp.Jednostka", uczelnia=uczelnia)
    autor = baker.make(
        "bpp.Autor", aktualna_jednostka=jednostka, email="jan@uafm.edu.pl"
    )

    backend = _backend()
    backend.UserModel = get_user_model()

    user = backend.create_user(
        backend._normalized(
            {"preferred_username": "jkowalski", "mail": "jan@uafm.edu.pl"}
        )
    )

    user.refresh_from_db()
    assert user.autor_id == autor.pk


@pytest.mark.django_db
@override_settings(OIDC_LOGIN_SKROT="UAFM")
def test_create_user_nie_dopasowuje_autora_z_obcej_uczelni():
    # Autor istnieje w innej uczelni niż realm OIDC → konto bez powiązania.
    baker.make("bpp.Uczelnia", skrot="UAFM")
    obca = baker.make("bpp.Uczelnia", skrot="INNA")
    jednostka = baker.make("bpp.Jednostka", uczelnia=obca)
    baker.make("bpp.Autor", aktualna_jednostka=jednostka, email="jan@uafm.edu.pl")

    backend = _backend()
    backend.UserModel = get_user_model()

    user = backend.create_user(
        backend._normalized(
            {"preferred_username": "jkowalski", "mail": "jan@uafm.edu.pl"}
        )
    )

    user.refresh_from_db()
    assert user.autor_id is None


@pytest.mark.django_db
@override_settings(OIDC_LOGIN_SKROT="UAFM")
def test_update_user_dopasowuje_autora():
    # Konto założone wcześniej (bez autora) dostaje powiązanie przy kolejnym
    # logowaniu przez update_user.
    uczelnia = baker.make("bpp.Uczelnia", skrot="UAFM")
    jednostka = baker.make("bpp.Jednostka", uczelnia=uczelnia)
    autor = baker.make(
        "bpp.Autor", aktualna_jednostka=jednostka, email="jan@uafm.edu.pl"
    )

    UserModel = get_user_model()
    user = UserModel.objects.create_user(username="jkowalski", email="jan@uafm.edu.pl")

    backend = _backend()
    backend.UserModel = UserModel
    backend.update_user(user, {"email": "jan@uafm.edu.pl"})

    user.refresh_from_db()
    assert user.autor_id == autor.pk


@pytest.mark.django_db
@override_settings(OIDC_LOGIN_SKROT="")
def test_create_user_bez_skrotu_nie_przypisuje():
    baker.make("bpp.Uczelnia", skrot="UAFM")
    backend = _backend()
    backend.UserModel = get_user_model()

    user = backend.create_user({"preferred_username": "jkowalski"})

    assert user.accessible_uczelnie.count() == 0
