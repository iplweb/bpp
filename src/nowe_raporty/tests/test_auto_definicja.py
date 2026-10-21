"""Dodanie raportu flexible-reports w adminie zakłada mu DefinicjaRaportu.

Bez tego nowy ``Report`` nie trafia do menu "raporty" na stronie, a redaktor
musiał pamiętać o drugim kroku w innym miejscu panelu.
"""

import pytest
from django.urls import reverse
from flexible_reports.models import Report
from model_bakery import baker

from nowe_raporty.models import DefinicjaRaportu


def _dodaj_raport(client, title, slug):
    return client.post(
        reverse("admin:flexible_reports_report_add"),
        {
            "title": title,
            "slug": slug,
            "template": "<h1>{{ object }}</h1>",
            "reportelement_set-TOTAL_FORMS": "0",
            "reportelement_set-INITIAL_FORMS": "0",
            "reportelement_set-MIN_NUM_FORMS": "0",
            "reportelement_set-MAX_NUM_FORMS": "1000",
        },
    )


@pytest.mark.django_db
def test_dodanie_raportu_w_adminie_zaklada_nieaktywna_definicje(admin_client):
    res = _dodaj_raport(admin_client, "XXX YYY", "xxx-yyy")
    assert res.status_code == 302, res.content

    report = Report.objects.get(slug="xxx-yyy")
    definicja = DefinicjaRaportu.objects.get(report=report)
    assert definicja.nazwa == "XXX YYY"
    assert definicja.slug == "xxx-yyy"
    assert definicja.aktywny is False
    assert definicja.poziom == DefinicjaRaportu.POZIOM_UCZELNIA
    assert definicja.poziom_dostepu == DefinicjaRaportu.DOSTEP_ZALOGOWANI


@pytest.mark.django_db
def test_edycja_raportu_nie_zaklada_kolejnej_definicji(admin_client):
    _dodaj_raport(admin_client, "XXX YYY", "xxx-yyy")
    report = Report.objects.get(slug="xxx-yyy")

    res = admin_client.post(
        reverse("admin:flexible_reports_report_change", args=(report.pk,)),
        {
            "title": "XXX YYY poprawiony",
            "slug": "xxx-yyy",
            "template": "<h1>{{ object }}</h1>",
            "reportelement_set-TOTAL_FORMS": "0",
            "reportelement_set-INITIAL_FORMS": "0",
            "reportelement_set-MIN_NUM_FORMS": "0",
            "reportelement_set-MAX_NUM_FORMS": "1000",
        },
    )
    assert res.status_code == 302, res.content
    assert DefinicjaRaportu.objects.filter(report=report).count() == 1


@pytest.mark.django_db
def test_zajety_slug_definicji_dostaje_przyrostek(admin_client):
    baker.make(DefinicjaRaportu, slug="xxx-yyy")

    _dodaj_raport(admin_client, "XXX YYY", "xxx-yyy")

    report = Report.objects.get(slug="xxx-yyy")
    assert DefinicjaRaportu.objects.get(report=report).slug == "xxx-yyy-2"


@pytest.mark.django_db
def test_dlugi_tytul_i_slug_mieszcza_sie_w_definicji(admin_client):
    baker.make(DefinicjaRaportu, slug="a" * 50)

    _dodaj_raport(admin_client, "T" * 300, "a" * 50)

    report = Report.objects.get(slug="a" * 50)
    definicja = DefinicjaRaportu.objects.get(report=report)
    assert len(definicja.nazwa) == 200
    assert definicja.slug == "a" * 48 + "-2"


@pytest.mark.django_db
def test_klonowanie_raportu_zaklada_definicje_dla_klonu(admin_client):
    zrodlo = baker.make(Report, title="Raport X", slug="raport-x")

    res = admin_client.post(
        reverse("admin:flexible_reports_report_clone", args=(zrodlo.pk,))
    )
    assert res.status_code == 302

    klon = Report.objects.exclude(pk=zrodlo.pk).get()
    definicja = DefinicjaRaportu.objects.get(report=klon)
    assert definicja.aktywny is False
    assert definicja.slug == klon.slug


@pytest.mark.django_db
def test_raport_utworzony_poza_adminem_nie_dostaje_definicji():
    # Seeding i kod/testy tworzące Report programowo same decydują o definicji.
    report = baker.make(Report, slug="programowy")
    assert not DefinicjaRaportu.objects.filter(report=report).exists()
