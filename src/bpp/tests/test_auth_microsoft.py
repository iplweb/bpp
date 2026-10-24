"""Testy logowania Microsoft (Office 365): tenant i wiązanie kont po e-mailu."""

from types import SimpleNamespace
from unittest import mock

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.signals import user_logged_in
from django.contrib.messages import get_messages
from django.core import checks
from django.test import override_settings
from model_bakery import baker

from bpp.auth.microsoft_conf import (
    W_TENANT_ID,
    claims_match_tenant,
    may_link_existing_users,
    normalize_microsoft_tenant_id,
)
from bpp.checks import microsoft_tenant_check
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


HASLO = "poprawne-haslo-testowe-123"
OSTRZEZENIE = "trybie wielokatalogowym"
WIELOKATALOGOWE = ["", "common", "Common", "organizations", "consumers"]


@pytest.mark.parametrize("value", [None, "", "  "])
def test_normalize_tenant_pusty_to_common(value):
    assert normalize_microsoft_tenant_id(value) == "common"


@pytest.mark.parametrize("value", [TENANT, "uczelnia.onmicrosoft.com", "common"])
def test_normalize_tenant_zachowuje_wartosc(value):
    assert normalize_microsoft_tenant_id(f" {value} ") == value


@pytest.mark.parametrize("tenant", WIELOKATALOGOWE)
def test_check_ostrzega_przy_braku_konkretnego_tenanta(tenant):
    with override_settings(
        MICROSOFT_AUTH_CLIENT_ID="client-id", MICROSOFT_AUTH_TENANT_ID=tenant
    ):
        wynik = microsoft_tenant_check(None)
    assert len(wynik) == 1
    assert wynik[0].id == W_TENANT_ID == "bpp.W201"
    assert isinstance(wynik[0], checks.Warning)
    assert "MICROSOFT_AUTH_TENANT_ID" in wynik[0].hint
    assert "onmicrosoft.com" in wynik[0].hint


@pytest.mark.parametrize("tenant", [TENANT, "uczelnia.onmicrosoft.com"])
def test_check_brak_ostrzezenia_dla_konkretnego_tenanta(tenant):
    with override_settings(
        MICROSOFT_AUTH_CLIENT_ID="client-id", MICROSOFT_AUTH_TENANT_ID=tenant
    ):
        assert microsoft_tenant_check(None) == []


def test_check_brak_ostrzezenia_bez_logowania_microsoft():
    with override_settings(MICROSOFT_AUTH_CLIENT_ID="", MICROSOFT_AUTH_TENANT_ID=""):
        assert microsoft_tenant_check(None) == []


def test_check_zarejestrowany():
    assert microsoft_tenant_check in checks.registry.registry.get_checks()


# --- komunikat dla superusera po zalogowaniu --------------------------------


def _zaloguj(client, username):
    return client.post(
        "/admin/login/",
        {"username": username, "password": HASLO, "next": "/admin/"},
        follow=True,
    )


def _komunikaty(response):
    return [str(m) for m in get_messages(response.wsgi_request)]


@pytest.mark.django_db
@override_settings(
    MICROSOFT_AUTH_CLIENT_ID="client-id", MICROSOFT_AUTH_TENANT_ID="common"
)
def test_superuser_po_zalogowaniu_dostaje_ostrzezenie(client):
    get_user_model().objects.create_superuser(
        username="szef", password=HASLO, email="szef@example.com"
    )
    komunikaty = _komunikaty(_zaloguj(client, "szef"))
    assert any(OSTRZEZENIE in m and "onmicrosoft.com" in m for m in komunikaty), (
        komunikaty
    )


@pytest.mark.django_db
@override_settings(
    MICROSOFT_AUTH_CLIENT_ID="client-id", MICROSOFT_AUTH_TENANT_ID="common"
)
def test_zwykly_staff_nie_dostaje_ostrzezenia(client):
    user = baker.make(get_user_model(), username="staff1", is_staff=True)
    user.set_password(HASLO)
    user.save()
    komunikaty = _komunikaty(_zaloguj(client, "staff1"))
    assert not any(OSTRZEZENIE in m for m in komunikaty)


@pytest.mark.django_db
@override_settings(
    MICROSOFT_AUTH_CLIENT_ID="client-id", MICROSOFT_AUTH_TENANT_ID=TENANT
)
def test_superuser_konkretny_tenant_brak_ostrzezenia(client):
    get_user_model().objects.create_superuser(
        username="szef", password=HASLO, email="szef@example.com"
    )
    komunikaty = _komunikaty(_zaloguj(client, "szef"))
    assert not any(OSTRZEZENIE in m for m in komunikaty)


@pytest.mark.django_db
@override_settings(
    MICROSOFT_AUTH_CLIENT_ID="client-id", MICROSOFT_AUTH_TENANT_ID="common"
)
def test_blad_przy_ostrzezeniu_nie_blokuje_logowania(client, caplog):
    get_user_model().objects.create_superuser(
        username="szef", password=HASLO, email="szef@example.com"
    )
    with mock.patch(
        "bpp.auth.microsoft_conf.microsoft_tenant_warning",
        side_effect=RuntimeError("awaria"),
    ):
        response = _zaloguj(client, "szef")
    assert response.wsgi_request.user.is_authenticated
    assert "tenanta Microsoft" in caplog.text


def test_handler_podpiety_pod_user_logged_in():
    klucze = [klucz for klucz, *_ in user_logged_in.receivers]
    assert any(k[0] == "bpp.ostrzez_superusera_o_tenancie_microsoft" for k in klucze)


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


@pytest.mark.uruchom_tylko_z_microsoft_auth
@pytest.mark.django_db
@override_settings(MICROSOFT_AUTH_TENANT_ID=TENANT)
@pytest.mark.parametrize("email", ["", "   ", None])
def test_backend_pusty_email_nie_wiaze_z_kontem_bez_emaila(email):
    from microsoft_auth.models import MicrosoftAccount

    admin = baker.make(get_user_model(), email="", is_superuser=True, password="")
    baker.make(get_user_model(), email="", password="")
    liczba = get_user_model().objects.count()

    backend = _backend(_claims(email=email))
    assert backend._authenticate_microsoft_user() is None
    assert not MicrosoftAccount.objects.filter(user=admin).exists()
    assert get_user_model().objects.count() == liczba


@pytest.mark.uruchom_tylko_z_microsoft_auth
@pytest.mark.django_db
@override_settings(MICROSOFT_AUTH_TENANT_ID=TENANT, MICROSOFT_AUTH_LINK_BY_EMAIL=False)
def test_backend_email_innej_wielkosci_liter_nie_wiaze_z_superuserem():
    from microsoft_auth.models import MicrosoftAccount

    admin = baker.make(
        get_user_model(), email="jan@example.com", is_superuser=True, password=""
    )
    backend = _backend(_claims(email="Jan@Example.COM"))
    assert backend._authenticate_microsoft_user() is None
    assert not MicrosoftAccount.objects.filter(user=admin).exists()
    assert get_user_model().objects.filter(email__iexact="jan@example.com").count() == 1


@pytest.mark.uruchom_tylko_z_microsoft_auth
@pytest.mark.django_db
@override_settings(MICROSOFT_AUTH_TENANT_ID=TENANT)
def test_backend_zwykle_konto_wiazane_bez_wzgledu_na_wielkosc_liter():
    user = baker.make(get_user_model(), email="jan@example.com", password="")
    backend = _backend(_claims(email="JAN@example.com"))
    assert backend._authenticate_microsoft_user() == user


@pytest.mark.uruchom_tylko_z_microsoft_auth
@pytest.mark.django_db
@override_settings(MICROSOFT_AUTH_TENANT_ID=TENANT)
def test_backend_odswieza_nieaktualny_dokument_discovery():
    from microsoft_auth.models import MicrosoftAccount

    from bpp.auth.microsoft import BppMicrosoftAuthenticationBackend

    user = baker.make(get_user_model(), email="jan@example.com", password="")
    baker.make(MicrosoftAccount, microsoft_id="ms-sub-1", user=user)

    class _Client:
        def __init__(self):
            self.wywolania = 0

        def get_claims(self):
            return _claims()

        @property
        def openid_config(self):
            self.wywolania += 1
            if self.wywolania == 1:
                return {"issuer": "https://login.microsoftonline.com/{tenantid}/v2.0"}
            return {"issuer": ISSUER}

    backend = BppMicrosoftAuthenticationBackend()
    backend.microsoft = _Client()
    with mock.patch("bpp.auth.microsoft.cache") as cache:
        assert backend._authenticate_microsoft_user() == user
    assert cache.delete.called


# --- backend w trybie wielokatalogowym (brak konkretnego tenanta) -----------


@pytest.mark.uruchom_tylko_z_microsoft_auth
@pytest.mark.django_db
@pytest.mark.parametrize("tenant", ["common", "organizations"])
def test_backend_tryb_wielokatalogowy_loguje_powiazane_konto(tenant):
    from microsoft_auth.models import MicrosoftAccount

    user = baker.make(get_user_model(), email="jan@example.com", password="")
    baker.make(MicrosoftAccount, microsoft_id="ms-sub-1", user=user)

    backend = _backend(
        _claims(tid=OTHER_TENANT, iss=OTHER_ISSUER),
        issuer="https://login.microsoftonline.com/{tenantid}/v2.0",
    )
    with override_settings(MICROSOFT_AUTH_TENANT_ID=tenant):
        assert backend._authenticate_microsoft_user() == user


@pytest.mark.uruchom_tylko_z_microsoft_auth
@pytest.mark.django_db
@override_settings(
    MICROSOFT_AUTH_TENANT_ID="common", MICROSOFT_AUTH_LINK_BY_EMAIL=False
)
@pytest.mark.parametrize("attrs", [{"is_staff": True}, {"is_superuser": True}])
def test_backend_tryb_wielokatalogowy_nie_wiaze_konta_staff(attrs):
    from microsoft_auth.models import MicrosoftAccount

    konto = baker.make(get_user_model(), email="jan@example.com", password="", **attrs)
    backend = _backend(_claims(tid=OTHER_TENANT, iss=OTHER_ISSUER))
    assert backend._authenticate_microsoft_user() is None
    assert not MicrosoftAccount.objects.filter(user=konto).exists()


@pytest.mark.uruchom_tylko_z_microsoft_auth
@pytest.mark.django_db
@override_settings(
    MICROSOFT_AUTH_TENANT_ID="common", MICROSOFT_AUTH_LINK_BY_EMAIL=False
)
def test_backend_tryb_wielokatalogowy_nie_wiaze_konta_z_haslem():
    konto = baker.make(get_user_model(), email="jan@example.com")
    konto.set_password(HASLO)
    konto.save()
    backend = _backend(_claims())
    assert backend._authenticate_microsoft_user() is None


@pytest.mark.uruchom_tylko_z_microsoft_auth
@pytest.mark.django_db
@override_settings(MICROSOFT_AUTH_TENANT_ID="common")
def test_backend_tryb_wielokatalogowy_odmawia_przy_pustym_lub_wieloznacznym_emailu():
    baker.make(get_user_model(), email="jan@example.com", password="", _quantity=2)
    liczba = get_user_model().objects.count()
    assert _backend(_claims(email=""))._authenticate_microsoft_user() is None
    assert _backend(_claims(sub="ms-2"))._authenticate_microsoft_user() is None
    assert get_user_model().objects.count() == liczba
