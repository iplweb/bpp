"""Polityka haseł: min. 15 znaków, bez reguł złożoności, bez rotacji.

Zgodnie z NIST SP 800-63B (rev. 4): długość zamiast wymogów „cyfra + znak
specjalny", a wymuszona zmiana hasła tylko przy podejrzeniu kompromitacji.
"""

import secrets
from datetime import timedelta

import pytest
from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, password_validation
from django.contrib.sessions.backends.db import SessionStore
from django.core.exceptions import ValidationError
from django.test import RequestFactory
from django.urls import reverse
from django.utils import timezone
from password_policies.models import PasswordChangeRequired

from django_bpp.context_processors import conditional_password_status
from django_bpp.forms import BppPasswordChangeForm
from django_bpp.middleware import ConditionalPasswordChangeMiddleware

# Losowe, żeby skanery sekretów nie brały fikstury za wyciek danych logowania.
STARE_HASLO = secrets.token_urlsafe(16)


@pytest.fixture()
def dawny_uzytkownik(django_user_model):
    """Użytkownik, którego hasło przy rotacji 30-dniowej dawno by wygasło."""
    user = django_user_model.objects.create_user("dawny")
    user.set_password(STARE_HASLO)
    user.date_joined = timezone.now() - timedelta(days=365)
    user.save()
    return user


@pytest.fixture()
def zalogowany_request(dawny_uzytkownik):
    request = RequestFactory().get("/")
    request.user = dawny_uzytkownik
    request.session = SessionStore()
    request.session[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
    return request


def test_rotacja_hasel_domyslnie_wylaczona():
    assert settings.PASSWORD_DURATION_SECONDS == 0


@pytest.mark.django_db
def test_brak_komunikatu_o_przeterminowanym_hasle(zalogowany_request):
    assert conditional_password_status(zalogowany_request) == {
        "password_change_required": False
    }


@pytest.mark.django_db
def test_middleware_nie_wymusza_zmiany_hasla(zalogowany_request):
    middleware = ConditionalPasswordChangeMiddleware(lambda r: None)
    assert middleware.process_request(zalogowany_request) is None


@pytest.mark.django_db
def test_wymuszona_zmiana_dziala_mimo_wylaczonej_rotacji(
    zalogowany_request, dawny_uzytkownik
):
    # Admin może wymusić zmianę hasła (np. po podejrzeniu wycieku) wpisem
    # PasswordChangeRequired -- to nie jest rotacja i ma działać dalej.
    PasswordChangeRequired.objects.create(user=dawny_uzytkownik)
    middleware = ConditionalPasswordChangeMiddleware(lambda r: None)

    response = middleware.process_request(zalogowany_request)

    assert response.status_code == 302
    assert response.url.startswith(reverse("password_change"))
    assert conditional_password_status(zalogowany_request) == {
        "password_change_required": True
    }


@pytest.mark.django_db
def test_wymuszona_zmiana_nie_przekierowuje_ze_strony_zmiany_hasla(
    zalogowany_request, dawny_uzytkownik
):
    PasswordChangeRequired.objects.create(user=dawny_uzytkownik)
    zalogowany_request.path = zalogowany_request.path_info = reverse("password_change")
    middleware = ConditionalPasswordChangeMiddleware(lambda r: None)

    assert middleware.process_request(zalogowany_request) is None


def _formularz(user, haslo):
    return BppPasswordChangeForm(
        user,
        data={
            "old_password": STARE_HASLO,
            "new_password1": haslo,
            "new_password2": haslo,
        },
    )


@pytest.mark.django_db
@pytest.mark.parametrize(
    "haslo",
    [
        "ala ma kota i psa",  # pragma: allowlist secret
        "zielonaherbatazcytryna",  # pragma: allowlist secret
        "ŻółtaŁódźPłyniePoWiśle",  # pragma: allowlist secret
    ],
)
def test_formularz_przyjmuje_dlugie_haslo_bez_cyfr_i_symboli(dawny_uzytkownik, haslo):
    form = _formularz(dawny_uzytkownik, haslo)
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_formularz_podpowiada_minimalna_dlugosc(dawny_uzytkownik):
    form = BppPasswordChangeForm(dawny_uzytkownik)
    assert "Co najmniej 15 znaków" in form.fields["new_password1"].help_text


@pytest.mark.django_db
def test_formularz_podpowiada_czego_unikac_bez_gotowego_hasla(dawny_uzytkownik):
    # Wzorce do unikania opisane słowami — bez przykładowego hasła, które
    # ludzie przepisaliby jako własne.
    form = BppPasswordChangeForm(dawny_uzytkownik)
    help_text = form.fields["new_password1"].help_text
    assert "Unikaj imion, nazwisk, nazw miejscowości i dat" in help_text


@pytest.mark.django_db
def test_formularz_odrzuca_haslo_krotsze_niz_15_znakow(dawny_uzytkownik):
    form = _formularz(dawny_uzytkownik, "Kr0tk!e-haslo1")  # 14 znaków
    assert not form.is_valid()
    assert "new_password1" in form.errors


@pytest.mark.django_db
def test_formularz_odrzuca_powtorzone_znaki(dawny_uzytkownik):
    form = _formularz(dawny_uzytkownik, "aaaaaaaaaaaaaaaa")
    assert not form.is_valid()
    assert "new_password1" in form.errors


@pytest.mark.django_db
def test_walidatory_django_wymagaja_15_znakow(dawny_uzytkownik):
    # Te walidatory obowiązują poza formularzem password_policies: admin,
    # kreator pierwszego uruchomienia, createsuperuser.
    with pytest.raises(ValidationError):
        password_validation.validate_password("ala ma kota i ", dawny_uzytkownik)
    password_validation.validate_password("ala ma kota i p", dawny_uzytkownik)


@pytest.mark.django_db
def test_walidatory_django_odrzucaja_popularne_haslo(dawny_uzytkownik):
    with pytest.raises(ValidationError):
        password_validation.validate_password(
            "1q2w3e4r5t6y7u8i9o0p",
            dawny_uzytkownik,  # pragma: allowlist secret
        )
