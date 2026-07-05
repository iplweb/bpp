"""Faza B / issue #438 — I-2.

Testy nowej infrastruktury zastępującej 3 triggery bazodanowe sygnałami
Pythona (migracja 0455) oraz idempotentności konwersji Wydzial → Jednostka.
"""

import importlib
from datetime import date, timedelta

import pytest
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
#
# Faza B (#438), III-1: ``rerun_konwersja_wydzialy`` (ta funkcja) twardo
# koduje ``rodzaj_jednostki="normalna"`` — kolumnę, którą III-1 usuwa z
# modelu. Migracja 0455 jest NIENARUSZALNA (nie modyfikujemy istniejących
# migracji) i sama w sobie jest bezpieczna — działa na SWOIM historycznym
# stanie schematu (kolumna obecna), uruchamiana w prawdziwym łańcuchu
# migracji przez każdą świeżą instalację. Ale WYWOŁANIE JEJ WPROST przeciw
# ŻYWEMU modelowi (jak robiły poniższe testy) po zastosowaniu 0461 nie
# może już działać — i nie da się tego naprawić nawet modelami
# historycznymi, bo fizyczna kolumna w tabeli testowej bazy (po pełnym
# `migrate`) już nie istnieje. Testy kolizji/suffiksu niżej przepisano na
# bezpośrednie testowanie ``_bez_kolizji`` (algorytm suffiksowania —
# niezależny od CharField/FK, wciąż w pełni testowalny).
_mig_0455 = importlib.import_module("bpp.migrations.0455_faza_b_i2")
_bez_kolizji = _mig_0455._bez_kolizji


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
    migracji ``IntegrityError`` — helper 0455 (``_bez_kolizji``) dokleja
    deterministyczny suffiks wyprowadzony ze stabilnego ``Wydzial.id``
    (== ``legacy_wydzial_id``).

    Testujemy WPROST algorytm suffiksowania (patrz komentarz przy imporcie
    ``_bez_kolizji`` na górze pliku — pełne ``rerun_konwersja_wydzialy`` nie
    da się już wywołać bezpośrednio po III-1, bo koduje na sztywno usunięty
    CharField ``rodzaj_jednostki``; algorytm suffiksowania jest od tego
    niezależny i pozostaje w pełni testowalny).
    """
    u = baker.make(Uczelnia)

    # Istniejąca Jednostka rezerwuje nazwę i skrót (oba unique=True):
    baker.make(Jednostka, uczelnia=u, nazwa="Kolizja", skrot="KOL")

    # Wydzial utworzony przez stary kod w oknie A→B — te same nazwa/skrót:
    w = baker.make(Wydzial, uczelnia=u, nazwa="Kolizja", skrot="KOL", skrot_nazwy=None)

    nazwa = _bez_kolizji(Jednostka, "nazwa", w.nazwa, w.id, 512, f" [W{w.id}]")
    skrot = _bez_kolizji(Jednostka, "skrot", w.skrot, w.id, 128, f"-W{w.id}")
    skrot_nazwy = _bez_kolizji(
        Jednostka, "skrot_nazwy", w.skrot_nazwy, w.id, 250, f"-W{w.id}"
    )

    assert nazwa == f"Kolizja [W{w.id}]"
    assert skrot == f"KOL-W{w.id}"
    # Puste/None nie kolidują z niczym — zostaje bez zmian:
    assert skrot_nazwy is None

    # Idempotencja algorytmu: drugie wywołanie na JUŻ zasuffiksowanej
    # wartości nie koliduje z niczym (suffiks unikalny), więc nie
    # dokleja suffiksu powtórnie.
    nazwa_ponownie = _bez_kolizji(Jednostka, "nazwa", nazwa, w.id, 512, f" [W{w.id}]")
    assert nazwa_ponownie == nazwa


@pytest.mark.django_db
def test_konwersja_wydzialy_bez_kolizji_kopiuje_verbatim():
    """Bez kolizji helper 0455 (``_bez_kolizji``) kopiuje ``nazwa``/``skrot``
    bez suffiksu — auto-suffiks dotyka WYŁĄCZNIE pól, które faktycznie
    kolidują (patrz komentarz przy imporcie ``_bez_kolizji`` na górze pliku)."""
    u = baker.make(Uczelnia)
    w = baker.make(Wydzial, uczelnia=u, nazwa="Unikat", skrot="UNI", skrot_nazwy="Uni.")

    nazwa = _bez_kolizji(Jednostka, "nazwa", w.nazwa, w.id, 512, f" [W{w.id}]")
    skrot = _bez_kolizji(Jednostka, "skrot", w.skrot, w.id, 128, f"-W{w.id}")
    skrot_nazwy = _bez_kolizji(
        Jednostka, "skrot_nazwy", w.skrot_nazwy, w.id, 250, f"-W{w.id}"
    )

    assert nazwa == "Unikat"
    assert skrot == "UNI"
    assert skrot_nazwy == "Uni."
