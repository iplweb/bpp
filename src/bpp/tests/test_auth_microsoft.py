"""Testy logowania Microsoft (Office 365): tenant i wiązanie kont po e-mailu."""

from types import SimpleNamespace
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.core.exceptions import ImproperlyConfigured
from django.test import override_settings
from model_bakery import baker

from bpp.auth.microsoft_conf import (
    claims_match_tenant,
    may_link_existing_users,
    validate_microsoft_tenant_id,
)
from django_bpp.external_auth import EXTERNAL_AUTH_BACKENDS, MICROSOFT_BACKEND

TENANT = "11111111-2222-3333-4444-555555555555"
OTHER_TENANT = "99999999-8888-7777-6666-555555555555"
ISSUER = f"https://login.microsoftonline.com/{TENANT}/v2.0"
OTHER_ISSUER = f"https://login.microsoftonline.com/{OTHER_TENANT}/v2.0"


def _claims(tid=TENANT, iss=ISSUER, **extra):
    data = {
        "sub": "ms-sub-1",
        "tid": tid,
        "iss": iss,
        "email": "jan@example.com",
        "preferred_username": "jan@example.com",
        "name": "Jan Kowalski",
    }
    data.update(extra)
    return data


# --- konfiguracja ---------------------------------------------------------


@pytest.mark.parametrize(
    "value", [None, "", "  ", "common", "Common", "organizations", "consumers"]
)
def test_validate_tenant_odrzuca_puste_i_wielotenantowe(value):
    with pytest.raises(ImproperlyConfigured):
        validate_microsoft_tenant_id(value)


@pytest.mark.parametrize("value", [TENANT, "uczelnia.onmicrosoft.com"])
def test_validate_tenant_akceptuje_konkretny_katalog(value):
    assert validate_microsoft_tenant_id(f" {value} ") == value


def test_backend_bpp_rozpoznawany_jako_zewnetrzny():
    assert MICROSOFT_BACKEND in EXTERNAL_AUTH_BACKENDS


# --- claimy tid / iss -----------------------------------------------------


def test_claims_zgodny_tenant_guid():
    assert claims_match_tenant(_claims(), TENANT, ISSUER)


def test_claims_tenant_jako_domena_weryfikowany_po_issuerze():
    assert claims_match_tenant(_claims(), "uczelnia.onmicrosoft.com", ISSUER)


def test_claims_inny_tid_odrzucony():
    assert not claims_match_tenant(
        _claims(tid=OTHER_TENANT, iss=OTHER_ISSUER), TENANT, ISSUER
    )


def test_claims_inny_tid_odrzucony_dla_tenanta_domenowego():
    assert not claims_match_tenant(
        _claims(tid=OTHER_TENANT, iss=OTHER_ISSUER),
        "uczelnia.onmicrosoft.com",
        ISSUER,
    )


def test_claims_tid_niespojny_z_iss_odrzucony():
    assert not claims_match_tenant(_claims(tid=OTHER_TENANT), TENANT, ISSUER)


@pytest.mark.parametrize("brak", ["tid", "iss"])
def test_claims_bez_tid_lub_iss_odrzucone(brak):
    claims = _claims()
    del claims[brak]
    assert not claims_match_tenant(claims, TENANT, ISSUER)


def test_claims_issuer_szablonowy_odrzucony():
    template = "https://login.microsoftonline.com/{tenantid}/v2.0"
    assert not claims_match_tenant(_claims(), TENANT, template)


def test_claims_brak_expected_issuer_odrzucony():
    assert not claims_match_tenant(_claims(), TENANT, None)


# --- decyzja o wiązaniu po e-mailu -----------------------------------------


@pytest.mark.django_db
def test_link_brak_istniejacego_usera_dozwolony():
    assert may_link_existing_users([], link_by_email=False)


@pytest.mark.django_db
@pytest.mark.parametrize(
    "attrs",
    [{"is_superuser": True}, {"is_staff": True}],
)
def test_link_konto_uprzywilejowane_zablokowane(attrs):
    user = baker.make(get_user_model(), password="", **attrs)
    assert not may_link_existing_users([user], link_by_email=False)


@pytest.mark.django_db
def test_link_konto_z_haslem_lokalnym_zablokowane():
    user = baker.make(get_user_model())
    user.set_password("haslo-lokalne-123")
    user.save()
    assert not may_link_existing_users([user], link_by_email=False)


@pytest.mark.django_db
def test_link_zwykle_konto_bez_hasla_dozwolone():
    bez_hasla = baker.make(get_user_model(), password="")
    nieuzywalne = baker.make(get_user_model())
    nieuzywalne.set_unusable_password()
    nieuzywalne.save()
    assert may_link_existing_users([bez_hasla], link_by_email=False)
    assert may_link_existing_users([nieuzywalne], link_by_email=False)


@pytest.mark.django_db
def test_link_wlaczony_flaga_pozwala_na_konto_uprzywilejowane():
    user = baker.make(get_user_model(), is_superuser=True, password="")
    assert may_link_existing_users([user], link_by_email=True)


@pytest.mark.django_db
def test_link_wielu_pasujacych_userow_zablokowane():
    users = baker.make(get_user_model(), password="", _quantity=2)
    assert not may_link_existing_users(users, link_by_email=True)


# --- backend (wymaga zainstalowanego microsoft_auth) ------------------------


def _backend(claims, issuer=ISSUER):
    from bpp.auth.microsoft import BppMicrosoftAuthenticationBackend

    backend = BppMicrosoftAuthenticationBackend()
    backend.microsoft = SimpleNamespace(
        get_claims=lambda: claims, openid_config={"issuer": issuer}
    )
    return backend


@pytest.mark.uruchom_tylko_z_microsoft_auth
@pytest.mark.django_db
@override_settings(MICROSOFT_AUTH_TENANT_ID=TENANT)
def test_backend_token_z_innego_tenanta_brak_logowania():
    from microsoft_auth.models import MicrosoftAccount

    user = baker.make(get_user_model(), email="jan@example.com", password="")
    baker.make(MicrosoftAccount, microsoft_id="ms-sub-1", user=user)

    backend = _backend(_claims(tid=OTHER_TENANT, iss=OTHER_ISSUER))
    assert backend._authenticate_microsoft_user() is None


@pytest.mark.uruchom_tylko_z_microsoft_auth
@pytest.mark.django_db
@override_settings(MICROSOFT_AUTH_TENANT_ID=TENANT)
def test_backend_token_z_innego_tenanta_nie_zaklada_konta():
    from microsoft_auth.models import MicrosoftAccount

    backend = _backend(_claims(tid=OTHER_TENANT, iss=OTHER_ISSUER, sub="obcy"))
    assert backend._authenticate_microsoft_user() is None
    assert not MicrosoftAccount.objects.filter(microsoft_id="obcy").exists()


@pytest.mark.uruchom_tylko_z_microsoft_auth
@pytest.mark.django_db
@override_settings(MICROSOFT_AUTH_TENANT_ID=TENANT, MICROSOFT_AUTH_LINK_BY_EMAIL=False)
def test_backend_nowe_konto_ms_nie_wiaze_sie_z_superuserem():
    from microsoft_auth.models import MicrosoftAccount

    admin = baker.make(
        get_user_model(), email="jan@example.com", is_superuser=True, password=""
    )

    backend = _backend(_claims())
    assert backend._authenticate_microsoft_user() is None

    admin.refresh_from_db()
    assert not MicrosoftAccount.objects.filter(user=admin).exists()
    assert get_user_model().objects.filter(email="jan@example.com").count() == 1


@pytest.mark.uruchom_tylko_z_microsoft_auth
@pytest.mark.django_db
@override_settings(MICROSOFT_AUTH_TENANT_ID=TENANT, MICROSOFT_AUTH_LINK_BY_EMAIL=True)
def test_backend_flaga_link_by_email_wiaze_z_superuserem():
    from microsoft_auth.models import MicrosoftAccount

    admin = baker.make(
        get_user_model(), email="jan@example.com", is_superuser=True, password=""
    )

    backend = _backend(_claims())
    assert backend._authenticate_microsoft_user() == admin
    assert MicrosoftAccount.objects.get(microsoft_id="ms-sub-1").user == admin


@pytest.mark.uruchom_tylko_z_microsoft_auth
@pytest.mark.django_db
@override_settings(MICROSOFT_AUTH_TENANT_ID=TENANT, MICROSOFT_AUTH_LINK_BY_EMAIL=False)
def test_backend_istniejace_powiazane_konto_loguje_sie():
    from microsoft_auth.models import MicrosoftAccount

    admin = baker.make(get_user_model(), email="jan@example.com", is_superuser=True)
    admin.set_password("haslo-lokalne-123")
    admin.save()
    baker.make(MicrosoftAccount, microsoft_id="ms-sub-1", user=admin)

    backend = _backend(_claims())
    assert backend._authenticate_microsoft_user() == admin


@pytest.mark.uruchom_tylko_z_microsoft_auth
@pytest.mark.django_db
@override_settings(MICROSOFT_AUTH_TENANT_ID=TENANT)
def test_backend_nowy_uzytkownik_jest_zakladany():
    backend = _backend(_claims(email="nowy@example.com", sub="ms-sub-nowy"))
    user = backend._authenticate_microsoft_user()
    assert user is not None
    assert user.email == "nowy@example.com"


@pytest.mark.uruchom_tylko_z_microsoft_auth
@pytest.mark.django_db
@override_settings(MICROSOFT_AUTH_TENANT_ID=TENANT)
def test_backend_authenticate_pelny_przeplyw(rf):
    from microsoft_auth.models import MicrosoftAccount

    from bpp.auth.microsoft import BppMicrosoftAuthenticationBackend

    user = baker.make(get_user_model(), email="jan@example.com", password="")
    baker.make(MicrosoftAccount, microsoft_id="ms-sub-1", user=user)

    def _client(claims):
        client = mock.MagicMock()
        client.fetch_token.return_value = {"access_token": "x", "scope": ["openid"]}
        client.valid_scopes.return_value = True
        client.get_claims.return_value = claims
        client.openid_config = {"issuer": ISSUER}
        return client

    request = rf.get("/microsoft/auth-callback/")
    with mock.patch("microsoft_auth.backends.MicrosoftClient") as klasa:
        klasa.return_value = _client(_claims())
        assert BppMicrosoftAuthenticationBackend().authenticate(request, "kod") == user

        klasa.return_value = _client(_claims(tid=OTHER_TENANT, iss=OTHER_ISSUER))
        assert BppMicrosoftAuthenticationBackend().authenticate(request, "kod") is None
