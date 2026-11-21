"""Okres ewaluacji: domyślny wg roku, wybór w sesji, przełącznik w belce."""

import pytest
from django.urls import reverse

from ewaluacja_common.models import OkresEwaluacji
from ewaluacja_common.okres import KLUCZ_SESJI, okres_domyslny


@pytest.mark.django_db
def test_okresy_z_migracji():
    assert [str(o) for o in OkresEwaluacji.objects.all()][:2] == [
        "2022–2025",
        "2026–2030",
    ]


@pytest.mark.django_db
@pytest.mark.parametrize(
    "rok,oczekiwany",
    [
        (2022, "2022–2025"),
        (2025, "2022–2025"),
        (2026, "2026–2030"),
        (2031, "2026–2030"),
    ],
)
def test_okres_domyslny_wg_roku(rok, oczekiwany):
    assert str(okres_domyslny(rok)) == oczekiwany


@pytest.mark.django_db
def test_okres_domyslny_przed_pierwszym_okresem():
    assert str(okres_domyslny(2000)) == "2022–2025"


@pytest.mark.django_db
def test_wybierz_okres_zapisuje_w_sesji(admin_client):
    okres = OkresEwaluacji.objects.get(rok_od=2022)
    resp = admin_client.post(
        reverse("ewaluacja_common:wybierz_okres"),
        {"okres": okres.pk, "next": "/ewaluacja_metryki/"},
    )
    assert resp.status_code == 302
    assert resp["Location"] == "/ewaluacja_metryki/"
    assert admin_client.session[KLUCZ_SESJI] == okres.pk


@pytest.mark.django_db
def test_wybierz_okres_nie_przekierowuje_poza_serwis(admin_client):
    okres = OkresEwaluacji.objects.first()
    resp = admin_client.post(
        reverse("ewaluacja_common:wybierz_okres"),
        {"okres": okres.pk, "next": "https://zly.example.com/"},
    )
    assert resp["Location"] == "/"


@pytest.mark.django_db
def test_wybierz_okres_wymaga_logowania(client):
    okres = OkresEwaluacji.objects.first()
    resp = client.post(reverse("ewaluacja_common:wybierz_okres"), {"okres": okres.pk})
    assert resp.status_code == 302
    assert KLUCZ_SESJI not in client.session


@pytest.mark.django_db
@pytest.mark.parametrize("wartosc", ["", "abc", "999999"])
def test_wybierz_okres_zla_wartosc_404(admin_client, wartosc):
    resp = admin_client.post(
        reverse("ewaluacja_common:wybierz_okres"), {"okres": wartosc}
    )
    assert resp.status_code == 404


@pytest.mark.django_db
def test_post_migrate_zaklada_okresy_gdy_tabela_pusta():
    """Po ``flush`` (TRUNCATE + post_migrate) okresy wracają."""
    from django.apps import apps

    from ewaluacja_common.okres import zasiej_okresy_po_migracji

    OkresEwaluacji.objects.all().delete()
    zasiej_okresy_po_migracji(apps.get_app_config("ewaluacja_common"))
    assert [str(o) for o in OkresEwaluacji.objects.all()] == [
        "2022–2025",
        "2026–2030",
    ]


@pytest.mark.django_db
def test_post_migrate_nie_rusza_niepustej_tabeli():
    from django.apps import apps

    from ewaluacja_common.okres import zasiej_okresy_po_migracji

    OkresEwaluacji.objects.all().delete()
    OkresEwaluacji.objects.create(rok_od=2026, rok_do=2029)
    zasiej_okresy_po_migracji(apps.get_app_config("ewaluacja_common"))
    assert [str(o) for o in OkresEwaluacji.objects.all()] == ["2026–2029"]


@pytest.mark.django_db(transaction=True)
def test_okresy_przezywaja_flush_testu_transakcyjnego():
    """Test transakcyjny przed nami zrobił flush — okresy muszą być."""
    assert OkresEwaluacji.objects.filter(rok_od=2022).exists()


@pytest.mark.django_db
def test_wybor_okresu_zapamietany_po_ponownym_zalogowaniu(client, admin_user):
    """Ostatnio wybrany okres jest domyślnym także w NOWEJ sesji."""
    from ewaluacja_common.models import WybranyOkresEwaluacji

    stary = OkresEwaluacji.objects.get(rok_od=2022)
    client.force_login(admin_user)
    client.post(reverse("ewaluacja_common:wybierz_okres"), {"okres": stary.pk})
    assert WybranyOkresEwaluacji.objects.get(user=admin_user).okres == stary

    client.logout()
    client.force_login(admin_user)
    assert KLUCZ_SESJI not in client.session
    resp = client.get(reverse("ewaluacja_metryki:lista"))
    assert resp.context["okres_ewaluacji"] == stary
    # ...i przechodząc po kolejnych stronach dalej ten sam:
    resp = client.get(reverse("ewaluacja_dwudyscyplinowcy:index"))
    assert resp.context["okres_ewaluacji"] == stary


@pytest.mark.django_db
def test_zmiana_wyboru_nadpisuje_zapamietany(admin_client, admin_user):
    from ewaluacja_common.models import WybranyOkresEwaluacji

    for rok_od in (2022, 2026):
        admin_client.post(
            reverse("ewaluacja_common:wybierz_okres"),
            {"okres": OkresEwaluacji.objects.get(rok_od=rok_od).pk},
        )
    assert WybranyOkresEwaluacji.objects.get(user=admin_user).okres.rok_od == 2026
    assert WybranyOkresEwaluacji.objects.count() == 1


@pytest.mark.django_db
def test_bez_wyboru_okres_domyslny(admin_client):
    resp = admin_client.get(reverse("ewaluacja_metryki:lista"))
    assert resp.context["okres_ewaluacji"] == okres_domyslny()


@pytest.mark.django_db
def test_admin_okresow_tylko_do_odczytu(admin_client):
    okres = OkresEwaluacji.objects.first()
    base = "admin:ewaluacja_common_okresewaluacji_"
    assert admin_client.get(reverse(base + "changelist")).status_code == 200
    assert admin_client.get(reverse(base + "add")).status_code == 403
    assert (
        admin_client.get(reverse(base + "delete", args=[okres.pk])).status_code == 403
    )
    # Widok zmiany dla superusera bez prawa zmiany = podgląd, POST nic nie zmienia.
    admin_client.post(
        reverse(base + "change", args=[okres.pk]),
        {"rok_od": okres.rok_od, "rok_do": 2099, "uwagi": "x"},
    )
    okres.refresh_from_db()
    assert okres.rok_do != 2099
