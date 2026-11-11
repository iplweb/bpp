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
