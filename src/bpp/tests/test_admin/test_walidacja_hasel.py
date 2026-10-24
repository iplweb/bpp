"""Walidacja siły haseł (AUTH_PASSWORD_VALIDATORS + password_policies)."""

import secrets

import pytest
from django.conf import settings
from django.contrib.auth.forms import AdminPasswordChangeForm
from django.urls import reverse
from model_bakery import baker

from bpp.admin import BppUserCreationForm
from bpp.models import BppUser
from django_bpp.forms import BppPasswordChangeForm
from django_bpp.password_validation import SimplePatternPasswordValidator

MOCNE_HASLO = "wrzos-kaktus-lipa-7"  # pragma: allowlist secret  # noqa: S105

SLABE_HASLA = [
    ("1", "password_too_short"),
    ("password123", "password_too_common"),
    ("moje-zielone-bpp-haslo", "password_context_word"),
    ("111111111111111", "password_repeated_character"),
    ("aaaaaaaaaaaaaaa", "password_repeated_character"),
    ("abababababababab", "password_too_few_unique_characters"),
    ("123456789012345", "password_simple_sequence"),
    ("abcdefghijklmno", "password_simple_sequence"),
    ("onmlkjihgfedcba", "password_simple_sequence"),
    ("qwertyuiopasdfg", "password_simple_sequence"),
    # Powtórzony fragment, także z urwaną ostatnią kopią (zxcvbn ocenia
    # urwaną końcówkę jak losowe znaki i daje takiemu hasłu 4/4).
    ("robak1robak1robak", "password_repeated_pattern"),
    ("Robak1robak1ROBAK1", "password_repeated_pattern"),
    ("pies1pies1pies1pi", "password_repeated_pattern"),
]


LOGIN = "nowy"
STARE_HASLO = secrets.token_urlsafe(16)


def _dane_hasla(haslo):
    return dict.fromkeys(("password1", "password2"), haslo)


def _dane_konta(haslo):
    return {**_dane_hasla(haslo), "username": LOGIN}


def _kody_bledow(form, pole):
    return {e.code for e in form.errors.as_data().get(pole, [])}


def test_minimalna_dlugosc_spojna_z_password_policies():
    from password_policies.conf import settings as pp_settings

    walidator = next(
        v
        for v in settings.AUTH_PASSWORD_VALIDATORS
        if v["NAME"].endswith("MinimumLengthValidator")
    )
    assert walidator["OPTIONS"]["min_length"] == settings.PASSWORD_MIN_LENGTH
    assert pp_settings.PASSWORD_MIN_LENGTH == settings.PASSWORD_MIN_LENGTH


@pytest.mark.django_db
@pytest.mark.parametrize("haslo,kod", SLABE_HASLA)
def test_tworzenie_uzytkownika_odrzuca_slabe_haslo(haslo, kod):
    form = BppUserCreationForm(data=_dane_konta(haslo))
    assert not form.is_valid()
    assert kod in _kody_bledow(form, "password2")


@pytest.mark.django_db
def test_tworzenie_uzytkownika_przyjmuje_mocne_haslo():
    form = BppUserCreationForm(data=_dane_konta(MOCNE_HASLO))
    form.is_valid()
    # Formularz z fields="__all__" wymaga też pól spoza hasła (admin zawęża je
    # przez add_fieldsets) — tu sprawdzamy tylko brak błędów haseł.
    assert "password1" not in form.errors
    assert "password2" not in form.errors


@pytest.mark.django_db
@pytest.mark.parametrize("haslo,kod", SLABE_HASLA)
def test_admin_dodanie_uzytkownika_slabe_haslo(admin_client, haslo, kod):
    res = admin_client.post(
        reverse("admin:bpp_bppuser_add"),
        _dane_konta(haslo),
    )
    assert res.status_code == 200
    assert kod in _kody_bledow(res.context["adminform"].form, "password2")
    assert not BppUser.objects.filter(username=LOGIN).exists()


@pytest.mark.django_db
def test_admin_dodanie_uzytkownika_mocne_haslo(admin_client):
    res = admin_client.post(
        reverse("admin:bpp_bppuser_add"),
        _dane_konta(MOCNE_HASLO),
    )
    assert res.status_code == 302
    assert BppUser.objects.get(username=LOGIN).check_password(MOCNE_HASLO)


@pytest.mark.django_db
@pytest.mark.parametrize("haslo,kod", SLABE_HASLA)
def test_admin_ustawienie_hasla_odrzuca_slabe_haslo(haslo, kod):
    user = baker.make(BppUser, username="ktos")
    form = AdminPasswordChangeForm(user, data=_dane_hasla(haslo))
    assert not form.is_valid()
    assert kod in _kody_bledow(form, "password2")


@pytest.mark.django_db
def test_admin_ustawienie_hasla_przyjmuje_mocne_haslo():
    user = baker.make(BppUser, username="ktos")
    form = AdminPasswordChangeForm(user, data=_dane_hasla(MOCNE_HASLO))
    assert form.is_valid(), form.errors


@pytest.mark.django_db
@pytest.mark.parametrize("haslo,kod", SLABE_HASLA)
def test_zmiana_hasla_odrzuca_slabe_haslo(haslo, kod):
    user = baker.make(BppUser)
    user.set_password(STARE_HASLO)
    user.save()
    dane = dict.fromkeys(("new_password1", "new_password2"), haslo)
    dane["old_password"] = STARE_HASLO
    form = BppPasswordChangeForm(user, data=dane)
    assert not form.is_valid()
    assert kod in _kody_bledow(form, "new_password2")


@pytest.mark.parametrize(
    "haslo",
    [
        MOCNE_HASLO,
        "ala ma kota i psa",  # pragma: allowlist secret
        "ŻółtaŁódźPłyniePoWiśle",  # pragma: allowlist secret
        "mostek-zebra-1987-pliszka",  # pragma: allowlist secret
    ],
)
def test_walidator_wzorcow_przyjmuje_zwykle_hasla(haslo):
    SimplePatternPasswordValidator().validate(haslo)


def test_walidator_wzorcow_help_text():
    assert "5 różnych znaków" in SimplePatternPasswordValidator().get_help_text()
