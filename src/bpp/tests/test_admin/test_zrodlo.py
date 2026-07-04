"""Testy kolumn i filtrów adminu Zrodlo: mniswID + liczba publikacji."""

import pytest
from django.contrib import admin as django_admin
from django.test import RequestFactory
from django.urls import reverse
from model_bakery import baker

from bpp.admin.filters import MaPublikacjeFilter, MniswIdObecnyFilter
from bpp.admin.zrodlo import ZrodloAdmin
from bpp.models import Wydawnictwo_Ciagle, Zrodlo
from pbn_api.models import Journal


def _admin():
    return ZrodloAdmin(Zrodlo, django_admin.site)


def _request(admin_user):
    req = RequestFactory().get("/")
    req.user = admin_user
    return req


@pytest.mark.django_db
def test_liczba_prac_annotation(admin_user, zrodlo):
    baker.make(Wydawnictwo_Ciagle, zrodlo=zrodlo)
    baker.make(Wydawnictwo_Ciagle, zrodlo=zrodlo)
    puste = baker.make(Zrodlo, nazwa="Puste", skrot="Pu.")

    admin = _admin()
    qs = admin.get_queryset(_request(admin_user))

    z_full = qs.get(pk=zrodlo.pk)
    z_empty = qs.get(pk=puste.pk)

    assert z_full._liczba_prac == 2
    assert admin.liczba_prac_display(z_full) == 2
    assert z_empty._liczba_prac == 0
    assert admin.liczba_prac_display(z_empty) == 0


@pytest.mark.django_db
def test_mnisw_id_display(zrodlo):
    admin = _admin()

    # źródło z pbn_uid i mniswId
    z_z_mnisw = baker.make(
        Zrodlo,
        nazwa="Z mniswID",
        skrot="Z m.",
        pbn_uid=baker.make(Journal, mniswId=12345),
    )
    # źródło z pbn_uid, ale bez mniswId
    z_bez_mnisw = baker.make(
        Zrodlo,
        nazwa="Bez mniswID",
        skrot="B m.",
        pbn_uid=baker.make(Journal, mniswId=None),
    )
    # źródło bez pbn_uid w ogóle
    z_bez_pbn = zrodlo

    assert admin.mnisw_id_display(z_z_mnisw) == 12345
    assert admin.mnisw_id_display(z_bez_mnisw) is None
    assert admin.mnisw_id_display(z_bez_pbn) is None


@pytest.mark.django_db
def test_MaPublikacjeFilter(admin_user, zrodlo):
    baker.make(Wydawnictwo_Ciagle, zrodlo=zrodlo)
    puste = baker.make(Zrodlo, nazwa="Puste", skrot="Pu.")

    admin = _admin()
    base_qs = admin.get_queryset(_request(admin_user))

    f = MaPublikacjeFilter(None, {}, Zrodlo, admin)

    f.value = lambda *a, **kw: "tak"
    z_tak = f.queryset(None, base_qs)
    assert zrodlo in z_tak
    assert puste not in z_tak

    f.value = lambda *a, **kw: "nie"
    z_nie = f.queryset(None, base_qs)
    assert puste in z_nie
    assert zrodlo not in z_nie


@pytest.mark.django_db
def test_MniswIdObecnyFilter(zrodlo):
    z_z_mnisw = baker.make(
        Zrodlo,
        nazwa="Z mniswID",
        skrot="Z m.",
        pbn_uid=baker.make(Journal, mniswId=999),
    )
    z_bez_mnisw = baker.make(
        Zrodlo,
        nazwa="Bez mniswID",
        skrot="B m.",
        pbn_uid=baker.make(Journal, mniswId=None),
    )
    z_bez_pbn = zrodlo

    f = MniswIdObecnyFilter(None, {}, Zrodlo, None)

    f.value = lambda *a, **kw: "jest"
    z_jest = f.queryset(None, Zrodlo.objects.all())
    assert z_z_mnisw in z_jest
    assert z_bez_mnisw not in z_jest
    assert z_bez_pbn not in z_jest

    f.value = lambda *a, **kw: "brak"
    z_brak = f.queryset(None, Zrodlo.objects.all())
    assert z_bez_mnisw in z_brak
    assert z_bez_pbn in z_brak
    assert z_z_mnisw not in z_brak


@pytest.mark.django_db
def test_changelist_renderuje_sie_z_filtrami(admin_client, zrodlo):
    # Smoke: annotacja + ordering po polu z JOIN-a (pbn_uid__mniswId) oraz
    # nowe filtry nie mogą wywalić changelistu.
    baker.make(Wydawnictwo_Ciagle, zrodlo=zrodlo)
    baker.make(
        Zrodlo,
        nazwa="Z mniswID",
        skrot="Z m.",
        pbn_uid=baker.make(Journal, mniswId=42),
    )
    url = reverse("admin:bpp_zrodlo_changelist")

    assert admin_client.get(url).status_code == 200
    # sortowanie po kolumnie liczby prac (index 8 w list_display)
    assert admin_client.get(url, {"o": "8"}).status_code == 200
    # oba nowe filtry naraz
    assert (
        admin_client.get(url, {"ma_publikacje": "nie", "mnisw_id": "brak"}).status_code
        == 200
    )
