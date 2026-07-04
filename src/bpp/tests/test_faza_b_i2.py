"""Faza B / issue #438 — I-2.

Testy nowej infrastruktury zastępującej 3 triggery bazodanowe sygnałami
Pythona (migracja 0455) oraz idempotentności konwersji Wydzial → Jednostka.
"""

import importlib
from datetime import date, timedelta

import pytest
from django.apps import apps as global_apps
from django.core.management import call_command
from django.db import connection
from model_bakery import baker

from bpp.models import (
    Jednostka,
    Jednostka_Rodzic,
    RodzajJednostki,
    Uczelnia,
    Wydzial,
)


def _wezel(wydzial):
    """LAZY węzeł-lustro Jednostka dla wydziału (#438) — tworzony przy linku."""
    from bpp.models.struktura_konwersja import znajdz_lub_utworz_wezel_wydzialu

    return znajdz_lub_utworz_wezel_wydzialu(wydzial)[0]


# Moduł migracji ma nazwę zaczynającą się od cyfry — nie zaimportujemy go
# zwykłym ``import``; helper konwersji wyciągamy przez importlib, by testować
# DOKŁADNIE logikę RunPython z 0455 (nie proxy w komendzie Fazy A, która NIE
# ma auto-suffiksu kolizji).
_mig_0455 = importlib.import_module("bpp.migrations.0455_faza_b_i2")
rerun_konwersja_wydzialy = _mig_0455.rerun_konwersja_wydzialy


@pytest.mark.django_db
def test_sygnal_ustawia_wydzial_i_aktualna():
    """Po utworzeniu wpisu Jednostka_Rodzic przez ORM sygnał ustawia
    wydzial_id oraz aktualna na Jednostce (interim: bieżący wpis → True)."""
    u = baker.make(Uczelnia)
    w = baker.make(Wydzial, uczelnia=u)
    j = baker.make(Jednostka, uczelnia=u)

    assert j.wydzial is None

    Jednostka_Rodzic.objects.create(jednostka=j, parent=_wezel(w))

    j.refresh_from_db()
    # Faza B (#438), II-1: sygnał NIE utrzymuje już ``wydzial`` (denorm z MPTT
    # ``parent``); testujemy tylko ``aktualna``.
    assert j.aktualna is True


@pytest.mark.django_db
def test_sygnal_respektuje_aktualna_override_false():
    """aktualna_override ustawione (False) — sygnał NIE nadpisuje aktualna
    derywacją, mimo że bieżący wpis dałby True. wydzial_id nadal liczony."""
    u = baker.make(Uczelnia)
    w = baker.make(Wydzial, uczelnia=u)
    j = baker.make(Jednostka, uczelnia=u, aktualna_override=False)

    Jednostka_Rodzic.objects.create(jednostka=j, parent=_wezel(w))

    j.refresh_from_db()
    assert j.aktualna is False  # override wygrywa nad derywacją (True)


@pytest.mark.django_db
def test_sygnal_respektuje_aktualna_override_true():
    """aktualna_override=True wygrywa nawet gdy derywacja dałaby False
    (wpis zakończony w przeszłości)."""
    u = baker.make(Uczelnia)
    w = baker.make(Wydzial, uczelnia=u)
    j = baker.make(Jednostka, uczelnia=u, aktualna_override=True)

    Jednostka_Rodzic.objects.create(
        jednostka=j, parent=_wezel(w), do=date.today() - timedelta(days=5)
    )

    j.refresh_from_db()
    assert j.aktualna is True  # override wygrywa nad derywacją (False)


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


@pytest.mark.django_db
def test_konwersja_wydzialy_kolizja_nazwy_auto_suffiks():
    """Kolizja ``nazwa``/``skrot`` Wydziału z istniejącą Jednostką NIE wywala
    migracji ``IntegrityError`` — helper 0455 dokleja deterministyczny suffiks
    wyprowadzony ze stabilnego ``Wydzial.id`` (== ``legacy_wydzial_id``).

    To testuje DOKŁADNIE RunPython z migracji 0455 (helper importowany wprost),
    a nie komendę Fazy A, która kopiuje verbatim i nie broni się przed kolizją.
    """
    RodzajJednostki.objects.get_or_create(nazwa="Wydział")
    u = baker.make(Uczelnia)

    # Istniejąca Jednostka rezerwuje nazwę i skrót (oba unique=True):
    baker.make(Jednostka, uczelnia=u, nazwa="Kolizja", skrot="KOL")

    # Wydzial utworzony przez stary kod w oknie A→B — te same nazwa/skrót:
    w = baker.make(Wydzial, uczelnia=u, nazwa="Kolizja", skrot="KOL", skrot_nazwy=None)

    # Nie może rzucić IntegrityError:
    rerun_konwersja_wydzialy(global_apps, None)

    wezel = Jednostka.objects.get(legacy_wydzial_id=w.id)
    assert wezel.nazwa == f"Kolizja [W{w.id}]"
    assert wezel.skrot == f"KOL-W{w.id}"
    assert wezel.widoczna is False
    assert wezel.aktualna is False

    # Idempotencja: ponowny przebieg nie tworzy duplikatu ani nie suffiksuje
    # powtórnie (skip po legacy_wydzial_id na wejściu pętli).
    rerun_konwersja_wydzialy(global_apps, None)

    wezly = Jednostka.objects.filter(legacy_wydzial_id=w.id)
    assert wezly.count() == 1
    assert wezly.get().nazwa == f"Kolizja [W{w.id}]"


@pytest.mark.django_db
def test_konwersja_wydzialy_bez_kolizji_kopiuje_verbatim():
    """Bez kolizji helper 0455 kopiuje ``nazwa``/``skrot`` bez suffiksu —
    auto-suffiks dotyka WYŁĄCZNIE pól, które faktycznie kolidują."""
    RodzajJednostki.objects.get_or_create(nazwa="Wydział")
    u = baker.make(Uczelnia)
    w = baker.make(Wydzial, uczelnia=u, nazwa="Unikat", skrot="UNI", skrot_nazwy="Uni.")

    rerun_konwersja_wydzialy(global_apps, None)

    wezel = Jednostka.objects.get(legacy_wydzial_id=w.id)
    assert wezel.nazwa == "Unikat"
    assert wezel.skrot == "UNI"
    assert wezel.skrot_nazwy == "Uni."
