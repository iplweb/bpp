"""Ikona raportu w menu — wybierana w definicji, domyślnie zależna od poziomu."""

import pytest
from django.urls import reverse
from model_bakery import baker

from nowe_raporty.ikony import IKONY_FOUNDATION
from nowe_raporty.models import DefinicjaRaportu


@pytest.mark.django_db
def test_bez_wybranej_ikony_menu_bierze_ikone_poziomu():
    d = baker.make(DefinicjaRaportu, poziom=DefinicjaRaportu.POZIOM_AUTOR, ikona="")
    assert d.ikona_menu == "fi-torsos-all"


@pytest.mark.django_db
def test_wybrana_ikona_wygrywa_z_poziomem():
    d = baker.make(
        DefinicjaRaportu, poziom=DefinicjaRaportu.POZIOM_AUTOR, ikona="fi-graph-pie"
    )
    assert d.ikona_menu == "fi-graph-pie"


def test_domyslne_ikony_poziomow_sa_w_foncie():
    assert set(DefinicjaRaportu.IKONY.values()) <= set(IKONY_FOUNDATION)


def _dane_formularza(definicja, **zmiany):
    dane = {
        "nazwa": definicja.nazwa,
        "slug": definicja.slug,
        "poziom": definicja.poziom,
        "report": definicja.report_id,
        "kolejnosc": definicja.kolejnosc,
        "aktywny": "on",
        "poziom_dostepu": definicja.poziom_dostepu,
        "ikona": "",
    }
    dane.update(zmiany)
    return dane


@pytest.mark.django_db
def test_admin_pokazuje_siatke_ikon(admin_client):
    d = baker.make(DefinicjaRaportu, nazwa="XXX", slug="xxx")
    res = admin_client.get(
        reverse("admin:nowe_raporty_definicjaraportu_change", args=(d.pk,))
    )
    tresc = res.content.decode()
    assert 'value="fi-graph-pie"' in tresc
    assert '<i class="fi-graph-pie"' in tresc
    assert "foundation-icons." in tresc
    assert "wybor_ikony." in tresc


@pytest.mark.django_db
def test_admin_zapisuje_wybrana_ikone(admin_client):
    d = baker.make(DefinicjaRaportu, nazwa="XXX", slug="xxx")
    res = admin_client.post(
        reverse("admin:nowe_raporty_definicjaraportu_change", args=(d.pk,)),
        _dane_formularza(d, ikona="fi-graph-pie"),
    )
    assert res.status_code == 302, res.content
    d.refresh_from_db()
    assert d.ikona == "fi-graph-pie"


@pytest.mark.django_db
def test_admin_odrzuca_nieistniejaca_ikone(admin_client):
    d = baker.make(DefinicjaRaportu, nazwa="XXX", slug="xxx")
    res = admin_client.post(
        reverse("admin:nowe_raporty_definicjaraportu_change", args=(d.pk,)),
        _dane_formularza(d, ikona="fi-nie-ma-takiej"),
    )
    assert res.status_code == 200
    d.refresh_from_db()
    assert d.ikona == ""
