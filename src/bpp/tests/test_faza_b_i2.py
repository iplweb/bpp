"""Faza B / issue #438 — I-2.

Testy nowej infrastruktury zastępującej 3 triggery bazodanowe sygnałami
Pythona (migracja 0455) oraz idempotentności konwersji Wydzial → Jednostka.
"""

from datetime import date, timedelta

import pytest
from django.core.management import call_command
from django.db import connection
from model_bakery import baker

from bpp.models import (
    Jednostka,
    Jednostka_Wydzial,
    RodzajJednostki,
    Uczelnia,
    Wydzial,
)


@pytest.mark.django_db
def test_sygnal_ustawia_wydzial_i_aktualna():
    """Po utworzeniu wpisu Jednostka_Wydzial przez ORM sygnał ustawia
    wydzial_id oraz aktualna na Jednostce (interim: bieżący wpis → True)."""
    u = baker.make(Uczelnia)
    w = baker.make(Wydzial, uczelnia=u)
    j = baker.make(Jednostka, uczelnia=u)

    assert j.wydzial is None

    Jednostka_Wydzial.objects.create(jednostka=j, wydzial=w)

    j.refresh_from_db()
    assert j.wydzial == w
    assert j.aktualna is True


@pytest.mark.django_db
def test_sygnal_respektuje_aktualna_override_false():
    """aktualna_override ustawione (False) — sygnał NIE nadpisuje aktualna
    derywacją, mimo że bieżący wpis dałby True. wydzial_id nadal liczony."""
    u = baker.make(Uczelnia)
    w = baker.make(Wydzial, uczelnia=u)
    j = baker.make(Jednostka, uczelnia=u, aktualna_override=False)

    Jednostka_Wydzial.objects.create(jednostka=j, wydzial=w)

    j.refresh_from_db()
    assert j.aktualna is False  # override wygrywa nad derywacją (True)
    assert j.wydzial == w  # wydzial_id nadal derywowany


@pytest.mark.django_db
def test_sygnal_respektuje_aktualna_override_true():
    """aktualna_override=True wygrywa nawet gdy derywacja dałaby False
    (wpis zakończony w przeszłości)."""
    u = baker.make(Uczelnia)
    w = baker.make(Wydzial, uczelnia=u)
    j = baker.make(Jednostka, uczelnia=u, aktualna_override=True)

    Jednostka_Wydzial.objects.create(
        jednostka=j, wydzial=w, do=date.today() - timedelta(days=5)
    )

    j.refresh_from_db()
    assert j.aktualna is True  # override wygrywa nad derywacją (False)
    assert j.wydzial == w


@pytest.mark.django_db
def test_zdjete_triggery_nie_istnieja_w_pg_trigger():
    """Po migracji 0455 pg_catalog.pg_trigger NIE zawiera 3 zdjętych
    triggerów."""
    with connection.cursor() as cur:
        cur.execute("SELECT tgname FROM pg_catalog.pg_trigger")
        nazwy = {row[0] for row in cur.fetchall()}

    assert "bpp_jednostka_ustaw_wydzial_aktualna_trigger" not in nazwy
    assert "bpp_jednostka_wydzial_sprawdz_uczelnia_id_trigger" not in nazwy
    assert "bpp_jednostka_sprawdz_uczelnia_id_trigger" not in nazwy


@pytest.mark.django_db
def test_konwersja_wydzialy_idempotentna():
    """Konwersja Wydzial → ukryty węzeł Jednostka jest idempotentna: drugi
    przebieg nie tworzy duplikatów. Komenda Fazy A jest tu proxy dla logiki
    RunPython z migracji 0455 (identyczny warunek pominięcia po
    legacy_wydzial_id)."""
    RodzajJednostki.objects.get_or_create(nazwa="Wydział")

    u = baker.make(Uczelnia)
    w1 = baker.make(Wydzial, uczelnia=u)
    w2 = baker.make(Wydzial, uczelnia=u)

    call_command("konwertuj_wydzialy_na_jednostki")

    wezly = Jednostka.objects.filter(legacy_wydzial_id__in=[w1.id, w2.id])
    assert wezly.count() == 2

    # Drugi przebieg — nic nie dodaje:
    call_command("konwertuj_wydzialy_na_jednostki")

    assert Jednostka.objects.filter(legacy_wydzial_id__in=[w1.id, w2.id]).count() == 2
