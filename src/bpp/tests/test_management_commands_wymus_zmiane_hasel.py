"""Komenda ``wymus_zmiane_hasel`` — wymusza zmianę hasła przy najbliższym
wejściu na stronę (wpis ``PasswordChangeRequired``) użytkownikom, którzy
logują się loginem i hasłem BPP."""

import secrets
from io import StringIO

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core.management import CommandError, call_command
from model_bakery import baker
from password_policies.models import PasswordChangeRequired


def _uzytkownik(username, is_active=True):
    user = baker.make(get_user_model(), username=username, is_active=is_active)
    user.set_password(secrets.token_urlsafe(16))
    user.save()
    return user


def _bez_hasla(username):
    user = baker.make(get_user_model(), username=username, is_active=True)
    user.set_unusable_password()
    user.save()
    return user


def _uruchom(*args):
    out = StringIO()
    call_command("wymus_zmiane_hasel", *args, stdout=out)
    return out.getvalue()


def _wymuszeni():
    return set(PasswordChangeRequired.objects.values_list("user__username", flat=True))


@pytest.mark.django_db
def test_wymusza_dla_aktywnych_z_haslem_bpp():
    _uzytkownik("ala")
    _uzytkownik("ola")
    _uzytkownik("nieaktywny", is_active=False)
    _bez_hasla("tylko-oauth")

    out = _uruchom()

    assert _wymuszeni() == {"ala", "ola"}
    assert "2" in out


@pytest.mark.django_db
def test_dry_run_niczego_nie_zapisuje():
    _uzytkownik("ala")

    out = _uruchom("--dry-run")

    assert _wymuszeni() == set()
    assert "ala" in out


@pytest.mark.django_db
def test_ponowne_uruchomienie_nie_dubluje_wpisow():
    ala = _uzytkownik("ala")
    PasswordChangeRequired.objects.create(user=ala)
    _uzytkownik("ola")

    _uruchom()
    _uruchom()

    assert PasswordChangeRequired.objects.count() == 2


@pytest.mark.django_db
def test_zaweza_do_loginow():
    _uzytkownik("ala")
    _uzytkownik("ola")
    _uzytkownik("ewa")

    _uruchom("--username", "ala", "--username", "ewa")

    assert _wymuszeni() == {"ala", "ewa"}


@pytest.mark.django_db
def test_nieznany_login_to_blad():
    _uzytkownik("ala")

    with pytest.raises(CommandError, match="nieistniejacy"):
        _uruchom("--username", "ala", "--username", "nieistniejacy")

    assert _wymuszeni() == set()


@pytest.mark.django_db
def test_zaweza_do_grupy():
    redaktorzy = baker.make(Group, name="redaktorzy-test")
    _uzytkownik("ala").groups.add(redaktorzy)
    _uzytkownik("ola")

    _uruchom("--grupa", "redaktorzy-test")

    assert _wymuszeni() == {"ala"}


@pytest.mark.django_db
def test_nieznana_grupa_to_blad():
    with pytest.raises(CommandError, match="nie-ma-takiej"):
        _uruchom("--grupa", "nie-ma-takiej")
