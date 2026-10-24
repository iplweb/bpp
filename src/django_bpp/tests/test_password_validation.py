"""Walidatory haseł: słowa kontekstowe i wycieki (HIBP)."""

import hashlib
import logging
from unittest import mock

import pytest
import requests
from django.contrib.auth import password_validation
from django.contrib.sites.models import Site
from django.core.exceptions import ValidationError
from django.db import ProgrammingError
from model_bakery import baker

from bpp.models import Uczelnia
from django_bpp.password_validation import (
    ContextWordsPasswordValidator,
    PwnedPasswordValidator,
    ZxcvbnPasswordValidator,
)

HASLO = "wrzos-kaktus-lipa-7"  # pragma: allowlist secret  # noqa: S105
SKROT = hashlib.sha1(HASLO.encode(), usedforsecurity=False).hexdigest().upper()

GET = "django_bpp.password_validation.requests.get"


def _kod(validator, haslo):
    with pytest.raises(ValidationError) as e:
        validator.validate(haslo)
    return e.value.code


# --- słowa kontekstowe -------------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "haslo",
    ["moje-zielone-BPP-haslo", "Bibliografia-pracownikow-2026"],
)
def test_kontekst_odrzuca_nazwe_serwisu(haslo):
    assert _kod(ContextWordsPasswordValidator(), haslo) == "password_context_word"


@pytest.mark.django_db
def test_kontekst_odrzuca_nazwe_i_skrot_uczelni_bez_polskich_znakow():
    baker.make(Uczelnia, nazwa="Politechnika Łódzka", skrot="PŁÓDZ")
    v = ContextWordsPasswordValidator()
    assert _kod(v, "zielony-lodzka-kot") == "password_context_word"
    assert _kod(v, "zielony-PLODZ-kot") == "password_context_word"
    v.validate("zielony-ogrod-kot")


@pytest.mark.django_db
def test_kontekst_odrzuca_domene_serwisu():
    Site.objects.update_or_create(id=1, defaults={"domain": "www.umlub.pl"})
    v = ContextWordsPasswordValidator()
    assert _kod(v, "haslo-umlub-zielone") == "password_context_word"
    # „www” i domena najwyższego poziomu nie są słowami kontekstowymi.
    v.validate("plaski-wwwiatrak-zielony")


@pytest.mark.django_db
def test_kontekst_slowa_z_konfiguracji(settings):
    settings.BPP_HASLA_SLOWA_KONTEKSTOWE = ["Kasztanowa", "ab"]
    v = ContextWordsPasswordValidator()
    assert _kod(v, "ulica-kasztanowa-17") == "password_context_word"
    # Słowa krótsze niż 3 znaki są pomijane.
    v.validate("zabawa-w-ogrodzie")


@pytest.mark.django_db
def test_kontekst_bez_tabel_nie_wywala_walidacji():
    with mock.patch.object(
        Uczelnia.objects, "values_list", side_effect=ProgrammingError("brak tabeli")
    ):
        v = ContextWordsPasswordValidator()
        assert _kod(v, "moje-bpp-haslo-zielone") == "password_context_word"
        v.validate(HASLO)


@pytest.mark.django_db
def test_kontekst_bez_uczelni_przyjmuje_zwykle_haslo():
    Uczelnia.objects.all().delete()
    ContextWordsPasswordValidator().validate(HASLO)


# --- Have I Been Pwned -------------------------------------------------------


def _odpowiedz(text="", status=200):
    return mock.Mock(status_code=status, text=text)


@pytest.fixture
def pwned_wlaczony(settings):
    settings.BPP_HASLA_SPRAWDZAJ_WYCIEKI = True


def test_pwned_trafienie_odrzuca(pwned_wlaczony):
    tekst = f"0000000000000000000000000000000000A:3\r\n{SKROT[5:]}:42\r\n"
    with mock.patch(GET, return_value=_odpowiedz(tekst)):
        assert _kod(PwnedPasswordValidator(), HASLO) == "password_pwned"


def test_pwned_brak_trafienia_przepuszcza(pwned_wlaczony):
    # Wpis z licznikiem 0 to padding (Add-Padding) — nie trafienie.
    tekst = f"0000000000000000000000000000000000A:3\r\n{SKROT[5:]}:0\r\n"
    with mock.patch(GET, return_value=_odpowiedz(tekst)):
        PwnedPasswordValidator().validate(HASLO)


def test_pwned_wysyla_tylko_prefiks(pwned_wlaczony):
    with mock.patch(GET, return_value=_odpowiedz("")) as get:
        PwnedPasswordValidator().validate(HASLO)
    (url,), kwargs = get.call_args
    assert url == f"https://api.pwnedpasswords.com/range/{SKROT[:5]}"
    assert SKROT[5:] not in repr(get.call_args)
    assert HASLO not in repr(get.call_args)
    assert kwargs["headers"]["Add-Padding"] == "true"
    assert "BPP" in kwargs["headers"]["User-Agent"]
    assert kwargs["timeout"] <= 5


@pytest.mark.parametrize(
    "awaria",
    [requests.Timeout("t"), requests.ConnectionError("c")],
)
def test_pwned_awaria_sieci_przepuszcza_i_ostrzega(pwned_wlaczony, caplog, awaria):
    with caplog.at_level(logging.WARNING, logger="django_bpp.password_validation"):
        with mock.patch(GET, side_effect=awaria):
            PwnedPasswordValidator().validate(HASLO)
    assert caplog.records
    assert HASLO not in caplog.text
    assert SKROT not in caplog.text


def test_pwned_status_inny_niz_200_przepuszcza(pwned_wlaczony, caplog):
    with caplog.at_level(logging.WARNING, logger="django_bpp.password_validation"):
        with mock.patch(GET, return_value=_odpowiedz("", status=503)):
            PwnedPasswordValidator().validate(HASLO)
    assert "503" in caplog.text


def test_pwned_wylacznik(settings):
    settings.BPP_HASLA_SPRAWDZAJ_WYCIEKI = False
    with mock.patch(GET) as get:
        PwnedPasswordValidator().validate(HASLO)
    get.assert_not_called()


@pytest.mark.django_db
def test_pwned_w_validate_password(pwned_wlaczony):
    tekst = f"{SKROT[5:]}:7\r\n"
    with mock.patch(GET, return_value=_odpowiedz(tekst)):
        with pytest.raises(ValidationError) as e:
            password_validation.validate_password(HASLO)
    assert "password_pwned" in {err.code for err in e.value.error_list}


def test_help_texty_po_polsku():
    assert "wycieków" in PwnedPasswordValidator().get_help_text()
    assert "uczelni" in ContextWordsPasswordValidator().get_help_text()
    assert "odgadnięcia" in ZxcvbnPasswordValidator().get_help_text()


# --- zxcvbn (siła hasła liczona lokalnie) -----------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "haslo,podpowiedz",
    [
        ("qwertyuiop123456", "popularne"),
        ("kochamcie1234567", "popularne"),
        ("P@ssw0rdP@ssw0rd", "powtórz"),
    ],
)
def test_zxcvbn_odrzuca_hasla_latwe_do_odgadniecia(haslo, podpowiedz):
    with pytest.raises(ValidationError) as e:
        ZxcvbnPasswordValidator().validate(haslo)
    assert e.value.code == "password_too_guessable"
    assert podpowiedz in str(e.value.message % e.value.params)


@pytest.mark.django_db
@pytest.mark.parametrize("haslo", [HASLO, "zielonaherbatazcytryna"])
def test_zxcvbn_przyjmuje_mocne_haslo(haslo):
    ZxcvbnPasswordValidator().validate(haslo)


@pytest.mark.django_db
def test_zxcvbn_uwzglednia_dane_uzytkownika():
    # Nazwisko spoza słowników zxcvbn: bez danych konta hasło jest mocne,
    # z nazwiskiem użytkownika (także po zdjęciu polskich znaków) — słabe.
    haslo = "wrzeszczynski1987!"
    ZxcvbnPasswordValidator().validate(haslo)
    user = baker.prepare("bpp.BppUser", username="mw", last_name="Wrzeszczyński")
    with pytest.raises(ValidationError):
        ZxcvbnPasswordValidator().validate(haslo, user=user)


@pytest.mark.django_db
def test_zxcvbn_uwzglednia_slowa_uczelni():
    haslo = "Przyrodniczy.2024"
    ZxcvbnPasswordValidator().validate(haslo)
    baker.make(Uczelnia, nazwa="Uniwersytet Przyrodniczy", skrot="UPRZ")
    with pytest.raises(ValidationError) as e:
        ZxcvbnPasswordValidator().validate(haslo)
    assert e.value.code == "password_too_guessable"


@pytest.mark.django_db
def test_zxcvbn_dlugie_haslo_nie_wywala_walidacji():
    # zxcvbn rzuca ValueError powyżej 72 znaków — oceniamy prefiks.
    ZxcvbnPasswordValidator().validate("wrzos-kaktus-lipa-7-" * 10)


def test_zxcvbn_wylaczony_przy_min_score_zero():
    ZxcvbnPasswordValidator(min_score=0).validate("aaaaaaaaaaaaaaaa")


def test_zxcvbn_min_score_z_ustawien(settings):
    settings.BPP_HASLA_MIN_SILA_ZXCVBN = 0
    ZxcvbnPasswordValidator().validate("aaaaaaaaaaaaaaaa")


# --- polski słownik zxcvbn -------------------------------------------------


@pytest.mark.django_db
@pytest.mark.parametrize(
    "haslo,powod",
    [
        ("słoneczko123456", "pospolite polskie słowa"),
        ("pomidorowa123456", "pospolite polskie słowa"),
        ("Malgorzata12345", "imiona"),
        ("Wojciechowski77", "nazwiska"),
    ],
)
def test_zxcvbn_odrzuca_polskie_slowo_imie_nazwisko_z_cyframi(haslo, powod):
    with pytest.raises(ValidationError) as e:
        ZxcvbnPasswordValidator().validate(haslo)
    assert powod in str(e.value.message % e.value.params)


@pytest.mark.django_db
def test_zxcvbn_fraza_z_kilku_polskich_slow_przechodzi():
    # Kilka słów to wg NIST dobre hasło — słownik nie może go odrzucać.
    ZxcvbnPasswordValidator().validate("ptaszek-na-drzewie-gra")
