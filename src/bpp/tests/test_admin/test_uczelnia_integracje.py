"""Konfiguracja integracji Uczelni (PBN, DSpace, ORCID, Clarivate) w adminie:
dostępna wyłącznie dla superużytkownika, sekrety write-only, walidacja
adresów API."""

import pytest
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType
from django.core.exceptions import ValidationError
from django.urls import reverse
from model_bakery import baker

from bpp.models import Uczelnia, Ukryj_Status_Korekty
from bpp.util import ssrf
from ewaluacja_liczba_n.models import LiczbaNDlaUczelni
from fixtures.conftest_browser import _webtest_login

SEKRETY = {
    "pbn_app_token": "SEKRET-PBN-TOKEN-123",
    "clarivate_password": "SEKRET-CLARIVATE-456",
    "orcid_client_secret": "SEKRET-ORCID-789",
    "dspace_api_password": "SEKRET-DSPACE-000",
}

POLA_INTEGRACJI = (
    "pbn_api_root",
    "pbn_app_name",
    "pbn_app_token",
    "pbn_api_user",
    "clarivate_username",
    "clarivate_password",
    "orcid_client_id",
    "orcid_client_secret",
    "dspace_api_endpoint",
    "dspace_api_username",
    "dspace_api_password",
)


@pytest.fixture
def uczelnia_z_integracjami(uczelnia):
    uczelnia.pbn_api_root = "https://pbn.nauka.gov.pl"
    uczelnia.pbn_app_name = "aplikacja"
    uczelnia.clarivate_username = "clar-user"
    uczelnia.orcid_client_id = "orcid-id"
    uczelnia.dspace_api_endpoint = "https://repo.example.org/server/api"
    uczelnia.dspace_api_username = "dspace-user"
    for pole, wartosc in SEKRETY.items():
        setattr(uczelnia, pole, wartosc)
    uczelnia.save()
    return uczelnia


@pytest.fixture
def struktura_app(webtest_app, django_user_model):
    user = django_user_model.objects.create_user(
        username="struktura_user", password="haslo-struktura", is_staff=True
    )
    grp, _ = Group.objects.get_or_create(name="struktura")
    for model in (Uczelnia, Ukryj_Status_Korekty, LiczbaNDlaUczelni):
        grp.permissions.add(
            *Permission.objects.filter(
                content_type=ContentType.objects.get_for_model(model)
            )
        )
    user.groups.add(grp)
    return _webtest_login(webtest_app, "struktura_user", "haslo-struktura")


def _url(uczelnia):
    return reverse("admin:bpp_uczelnia_change", args=(uczelnia.pk,))


@pytest.mark.django_db
def test_struktura_nie_widzi_konfiguracji_integracji(
    uczelnia_z_integracjami, struktura_app
):
    res = struktura_app.get(_url(uczelnia_z_integracjami))

    form = res.context["adminform"].form
    for pole in POLA_INTEGRACJI:
        assert pole not in form.fields
    for wartosc in SEKRETY.values():
        assert wartosc not in res.text
    assert "pbn.nauka.gov.pl" not in res.text


@pytest.mark.django_db
def test_struktura_post_nie_zmienia_konfiguracji_integracji(
    uczelnia_z_integracjami, struktura_app
):
    res = struktura_app.get(_url(uczelnia_z_integracjami))
    form = res.forms["uczelnia_form"]
    form["tytul_strony_glownej"] = "Zmieniony tytul"
    params = list(form.submit_fields()) + [
        ("pbn_api_root", "https://inny.example.com"),
        ("pbn_app_token", "NOWY"),
        ("dspace_api_endpoint", "https://inny.example.com/api"),
        ("dspace_api_password", "NOWE"),
        ("orcid_client_secret", "NOWY"),
        ("clarivate_password", "NOWE"),
    ]
    res2 = struktura_app.post(_url(uczelnia_z_integracjami), params=params)
    assert res2.status_code == 302, res2.text[:2000]

    u = Uczelnia.objects.get(pk=uczelnia_z_integracjami.pk)
    assert u.tytul_strony_glownej == "Zmieniony tytul"
    assert u.pbn_api_root == "https://pbn.nauka.gov.pl"
    assert u.dspace_api_endpoint == "https://repo.example.org/server/api"
    for pole, wartosc in SEKRETY.items():
        assert getattr(u, pole) == wartosc


@pytest.mark.django_db
def test_superuser_widzi_pola_ale_nie_wartosci_sekretow(
    uczelnia_z_integracjami, admin_app
):
    res = admin_app.get(_url(uczelnia_z_integracjami))

    form = res.context["adminform"].form
    for pole in POLA_INTEGRACJI:
        assert pole in form.fields
    for wartosc in SEKRETY.values():
        assert wartosc not in res.text


@pytest.mark.django_db
def test_superuser_pusty_sekret_zachowuje_wartosc(uczelnia_z_integracjami, admin_app):
    res = admin_app.get(_url(uczelnia_z_integracjami))
    form = res.forms["uczelnia_form"]
    for pole in SEKRETY:
        assert form[pole].value == ""
    form["orcid_client_secret"] = "NOWY-SEKRET-ORCID"
    form["tytul_strony_glownej"] = "Tytul superusera"
    res2 = form.submit()
    assert res2.status_code == 302, res2.text[:2000]

    from django.contrib.admin.models import LogEntry

    wpis = LogEntry.objects.filter(object_id=str(uczelnia_z_integracjami.pk)).latest(
        "action_time"
    )
    zmienione = wpis.get_change_message()
    assert "Token aplikacji w PBN" not in zmienione
    assert "ORCID Client Secret" in zmienione

    u = Uczelnia.objects.get(pk=uczelnia_z_integracjami.pk)
    assert u.tytul_strony_glownej == "Tytul superusera"
    assert u.orcid_client_secret == "NOWY-SEKRET-ORCID"
    for pole in ("pbn_app_token", "clarivate_password", "dspace_api_password"):
        assert getattr(u, pole) == SEKRETY[pole]


@pytest.mark.django_db
def test_superuser_adres_api_na_host_niepubliczny_odrzucony(
    uczelnia_z_integracjami, admin_app, monkeypatch
):
    monkeypatch.setattr(ssrf, "resolve_ips", lambda host: ["10.1.2.3"])
    res = admin_app.get(_url(uczelnia_z_integracjami))
    form = res.forms["uczelnia_form"]
    form["dspace_api_endpoint"] = "https://repo.wewnetrzny.example/api"
    res2 = form.submit()

    assert res2.status_code == 200
    assert "dspace_api_endpoint" in res2.context["adminform"].form.errors
    u = Uczelnia.objects.get(pk=uczelnia_z_integracjami.pk)
    assert u.dspace_api_endpoint == "https://repo.example.org/server/api"


@pytest.mark.django_db
def test_superuser_adres_api_na_host_publiczny_zapisany(
    uczelnia_z_integracjami, admin_app, monkeypatch
):
    monkeypatch.setattr(ssrf, "resolve_ips", lambda host: ["93.184.216.34"])
    res = admin_app.get(_url(uczelnia_z_integracjami))
    form = res.forms["uczelnia_form"]
    form["dspace_api_endpoint"] = "https://repo2.example.org/server/api"
    res2 = form.submit()

    assert res2.status_code == 302, res2.text[:2000]
    u = Uczelnia.objects.get(pk=uczelnia_z_integracjami.pk)
    assert u.dspace_api_endpoint == "https://repo2.example.org/server/api"


@pytest.mark.django_db
def test_struktura_zapis_nie_wykonuje_testu_polaczenia_pbn(
    uczelnia_z_integracjami, struktura_app, monkeypatch
):
    Uczelnia.objects.filter(pk=uczelnia_z_integracjami.pk).update(pbn_integracja=True)

    def _nie_wolno(self):
        raise AssertionError("pbn_client() nie powinien być wołany")

    monkeypatch.setattr(Uczelnia, "pbn_client", _nie_wolno)
    res = struktura_app.get(_url(uczelnia_z_integracjami))
    res2 = res.forms["uczelnia_form"].submit()
    assert res2.status_code == 302, res2.text[:2000]


@pytest.mark.parametrize(
    "url",
    [
        "http://127.0.0.1",
        "http://169.254.169.254",
        "https://10.0.0.1",
        "https://169.254.169.254/latest",
        "https://[::1]/api",
        "ftp://pbn.nauka.gov.pl",
    ],
)
@pytest.mark.django_db
def test_clean_odrzuca_adresy_niepubliczne(uczelnia, url, settings):
    settings.DEBUG = False
    for pole in Uczelnia.POLA_ADRESOW_INTEGRACJI:
        u = Uczelnia.objects.get(pk=uczelnia.pk)
        setattr(u, pole, url)
        with pytest.raises(ValidationError) as exc:
            u.clean()
        assert pole in exc.value.message_dict


@pytest.mark.django_db
def test_clean_przyjmuje_https_i_nie_waliduje_niezmienionych(uczelnia):
    u = Uczelnia.objects.get(pk=uczelnia.pk)
    u.pbn_api_root = "https://pbn.nauka.gov.pl"
    u.dspace_api_endpoint = "https://repo.example.org/server/api"
    u.clean()

    # Wartość zapisana wcześniej (np. przed wprowadzeniem walidacji) nie
    # blokuje zapisu innych pól.
    Uczelnia.objects.filter(pk=uczelnia.pk).update(
        dspace_api_endpoint="http://10.0.0.5/api"
    )
    u = Uczelnia.objects.get(pk=uczelnia.pk)
    u.tytul_strony_glownej = "Inny"
    u.clean()


def test_waliduj_url_integracji_dns_fail_closed(monkeypatch):
    def _boom(host):
        import socket

        raise socket.gaierror("brak")

    monkeypatch.setattr(ssrf, "resolve_ips", _boom)
    with pytest.raises(ValidationError):
        ssrf.waliduj_url_integracji("https://nieistniejacy.example")

    monkeypatch.setattr(ssrf, "resolve_ips", lambda h: ["93.184.216.34", "::1"])
    with pytest.raises(ValidationError):
        ssrf.waliduj_url_integracji("https://mieszany.example")


@pytest.mark.parametrize(
    "adres",
    [
        "100.64.0.1",
        "::ffff:127.0.0.1",
        "2002:7f00:1::",
        "2002:a9fe:a9fe::",
        "2001:0:4136:e378:8000:63bf:3fff:fdd2",
        "64:ff9b::a9fe:a9fe",
        "64:ff9b::a00:1",
        "fe80::1",
        "fc00::1",
        "224.0.0.1",
        "0.0.0.0",
    ],
)
def test_ip_is_public_odrzuca_adresy_niepubliczne(adres):
    import ipaddress

    assert not ssrf.ip_is_public(ipaddress.ip_address(adres))


@pytest.mark.parametrize(
    "adres", ["93.184.216.34", "2606:4700::1111", "64:ff9b::5db8:d822"]
)
def test_ip_is_public_przyjmuje_adresy_globalne(adres):
    import ipaddress

    assert ssrf.ip_is_public(ipaddress.ip_address(adres))


@pytest.mark.django_db
def test_struktura_nie_przywraca_wersji_z_historii(
    uczelnia_z_integracjami, struktura_app
):
    import reversion
    from reversion.models import Version

    with reversion.create_revision():
        uczelnia_z_integracjami.save()
    wersja = Version.objects.get_for_object(uczelnia_z_integracjami).first()

    url = reverse(
        "admin:bpp_uczelnia_revision",
        args=(uczelnia_z_integracjami.pk, wersja.pk),
    )
    assert struktura_app.get(url, expect_errors=True).status_code == 403
    url = reverse("admin:bpp_uczelnia_recover", args=(wersja.pk,))
    assert struktura_app.get(url, expect_errors=True).status_code == 403


@pytest.mark.django_db
def test_save_model_nie_superuser_zachowuje_konfiguracje_integracji(
    uczelnia_z_integracjami, rf, django_user_model
):
    from django.contrib import admin as django_admin

    from bpp.admin.uczelnia import UczelniaAdmin

    user = django_user_model.objects.create_user(
        username="nie_superuser", password="x", is_staff=True
    )
    request = rf.post("/")
    request.user = user
    model_admin = UczelniaAdmin(Uczelnia, django_admin.site)

    obj = Uczelnia.objects.get(pk=uczelnia_z_integracjami.pk)
    obj.pbn_api_root = "https://inny.example.com"
    obj.dspace_api_password = "NOWE"
    obj.pbn_app_token = "NOWY"
    obj.tytul_strony_glownej = "Nowy tytul"
    model_admin.save_model(request, obj, form=None, change=True)

    u = Uczelnia.objects.get(pk=uczelnia_z_integracjami.pk)
    assert u.tytul_strony_glownej == "Nowy tytul"
    assert u.pbn_api_root == "https://pbn.nauka.gov.pl"
    assert u.dspace_api_password == SEKRETY["dspace_api_password"]
    assert u.pbn_app_token == SEKRETY["pbn_app_token"]


@pytest.mark.django_db
def test_migracja_zamienia_http_na_https_w_adresach_integracji(uczelnia):
    import importlib

    from django.apps import apps

    migracja = importlib.import_module(
        "bpp.migrations.0495_uczelnia_adresy_integracji_https"
    )
    Uczelnia.objects.filter(pk=uczelnia.pk).update(
        pbn_api_root="http://pbn.nauka.gov.pl",
        dspace_api_endpoint="HTTP://repo.example.org/server/api",
    )
    druga = baker.make(Uczelnia, pbn_api_root="https://pbn.example.com")

    migracja.http_na_https(apps, None)

    u = Uczelnia.objects.get(pk=uczelnia.pk)
    assert u.pbn_api_root == "https://pbn.nauka.gov.pl"
    assert u.dspace_api_endpoint == "https://repo.example.org/server/api"
    druga.refresh_from_db()
    assert druga.pbn_api_root == "https://pbn.example.com"
    assert druga.dspace_api_endpoint == ""
