"""Faza B / issue #438 — IV-1 (migracja 0462).

Testy jednorazowego przeliczenia ``Jednostka.aktualna`` z historii (finalna
logika), ODKRYCIA (un-hide) węzłów-wydziałów wg ``Wydzial.widoczny``, spójności
komendy ``przelicz_aktualna`` z migracją oraz ujednoliconego sygnału
(brak wpisów ``Jednostka_Rodzic`` → ``aktualna=True``).
"""

from datetime import date, timedelta
from importlib import import_module

import pytest
from django.apps import apps as global_apps
from model_bakery import baker

from bpp.models import Jednostka, Jednostka_Rodzic, Uczelnia
from bpp.models.jednostka import przelicz_aktualna_wszystkich, wylicz_aktualna

_mig = import_module("bpp.migrations.0462_faza_b_iv1_przelicz_aktualna")

DZIS = date.today()
PRZESZLOSC = DZIS - timedelta(days=365)
DAWNO = DZIS - timedelta(days=3650)


@pytest.fixture
def uczelnia(db):
    return baker.make(Uczelnia)


def _jednostka(uczelnia, **kw):
    return baker.make(Jednostka, uczelnia=uczelnia, parent=None, **kw)


# ---------------------------------------------------------------------------
# Czysta funkcja derywacji (wylicz_aktualna) — 3 przypadki + override
# ---------------------------------------------------------------------------
def test_wylicz_aktualna_brak_wpisow_true():
    assert wylicz_aktualna(None, ma_wpis=False, override=None) is True


def test_wylicz_aktualna_do_null_true():
    assert wylicz_aktualna(None, ma_wpis=True, override=None) is True


def test_wylicz_aktualna_do_przeszlosc_false():
    assert wylicz_aktualna(PRZESZLOSC, ma_wpis=True, override=None) is False


def test_wylicz_aktualna_override_wygrywa():
    # override wygrywa nad każdą derywacją
    assert wylicz_aktualna(PRZESZLOSC, ma_wpis=True, override=True) is True
    assert wylicz_aktualna(None, ma_wpis=False, override=False) is False


# ---------------------------------------------------------------------------
# Inwariant na realnych modelach: aktualna == derywacja (override NULL) /
# aktualna == override (override ustawione), po jednorazowym przeliczeniu
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_recompute_brak_wpisow_true(uczelnia):
    j = _jednostka(uczelnia)
    # zepsuj wartość, żeby recompute miał co naprawić
    Jednostka.objects.filter(pk=j.pk).update(aktualna=False)

    przelicz_aktualna_wszystkich()

    j.refresh_from_db()
    assert j.aktualna is True


@pytest.mark.django_db
def test_recompute_do_null_true(uczelnia):
    j = _jednostka(uczelnia)
    baker.make(Jednostka_Rodzic, jednostka=j, parent=None, od=DAWNO, do=None)
    Jednostka.objects.filter(pk=j.pk).update(aktualna=False)

    przelicz_aktualna_wszystkich()

    j.refresh_from_db()
    assert j.aktualna is True


@pytest.mark.django_db
def test_recompute_do_przeszlosc_false(uczelnia):
    j = _jednostka(uczelnia)
    baker.make(Jednostka_Rodzic, jednostka=j, parent=None, od=DAWNO, do=PRZESZLOSC)
    Jednostka.objects.filter(pk=j.pk).update(aktualna=True)

    przelicz_aktualna_wszystkich()

    j.refresh_from_db()
    assert j.aktualna is False


@pytest.mark.django_db
def test_recompute_najswiezszy_wpis_wygrywa(uczelnia):
    """Bierze się NAJŚWIEŻSZY (max od) wpis — zamknięty stary + otwarty nowy
    → True."""
    j = _jednostka(uczelnia)
    baker.make(
        Jednostka_Rodzic,
        jednostka=j,
        parent=None,
        od=DAWNO,
        do=PRZESZLOSC,
    )
    baker.make(
        Jednostka_Rodzic,
        jednostka=j,
        parent=None,
        od=PRZESZLOSC + timedelta(days=1),
        do=None,
    )
    Jednostka.objects.filter(pk=j.pk).update(aktualna=False)

    przelicz_aktualna_wszystkich()

    j.refresh_from_db()
    assert j.aktualna is True


@pytest.mark.django_db
def test_recompute_override_wygrywa(uczelnia):
    # override=True mimo zamkniętego (przeszłego) wpisu:
    j_true = _jednostka(uczelnia, aktualna_override=True)
    baker.make(Jednostka_Rodzic, jednostka=j_true, parent=None, od=DAWNO, do=PRZESZLOSC)
    # override=False mimo braku wpisów (derywacja dałaby True):
    j_false = _jednostka(uczelnia, aktualna_override=False)

    przelicz_aktualna_wszystkich()

    j_true.refresh_from_db()
    j_false.refresh_from_db()
    assert j_true.aktualna is True
    assert j_false.aktualna is False


# ---------------------------------------------------------------------------
# Faza C (#438): testy kroku „odkryj_widoczna" / lazy-lustra (czytały
# ``Wydzial.widoczny`` przez struktura_konwersja) usunięto wraz z modelem
# Wydzial i struktura_konwersja.py — to była jednorazowa mechanika Fazy B.
# ---------------------------------------------------------------------------
# Spójność: komenda przelicz_aktualna == migracja 0462 (ten sam wynik)
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_komenda_i_migracja_daja_ten_sam_wynik(uczelnia):
    # Mieszany scenariusz pokrywający wszystkie gałęzie logiki:
    j_brak = _jednostka(uczelnia)  # brak wpisów → True
    j_open = _jednostka(uczelnia)
    baker.make(Jednostka_Rodzic, jednostka=j_open, parent=None, od=DAWNO, do=None)
    j_closed = _jednostka(uczelnia)
    baker.make(
        Jednostka_Rodzic, jednostka=j_closed, parent=None, od=DAWNO, do=PRZESZLOSC
    )
    j_ovr = _jednostka(uczelnia, aktualna_override=False)  # override False

    pks = [j_brak.pk, j_open.pk, j_closed.pk, j_ovr.pk]

    def _snapshot():
        return dict(Jednostka.objects.filter(pk__in=pks).values_list("pk", "aktualna"))

    # 1) Komenda (real models helper). Najpierw zepsuj, żeby recompute działał.
    Jednostka.objects.filter(pk__in=pks).update(aktualna=False)
    przelicz_aktualna_wszystkich()
    wynik_komenda = _snapshot()

    # 2) Migracja (historical models, inline logic). Znowu zepsuj.
    Jednostka.objects.filter(pk__in=pks).update(aktualna=False)
    _mig.przelicz_aktualna(global_apps, None)
    wynik_migracja = _snapshot()

    assert wynik_komenda == wynik_migracja
    # I konkretne wartości:
    assert wynik_komenda == {
        j_brak.pk: True,
        j_open.pk: True,
        j_closed.pk: False,
        j_ovr.pk: False,
    }


@pytest.mark.django_db
def test_migracja_idempotentna(uczelnia):
    j = _jednostka(uczelnia)
    baker.make(Jednostka_Rodzic, jednostka=j, parent=None, od=DAWNO, do=None)

    _mig.przelicz_aktualna(global_apps, None)
    j.refresh_from_db()
    pierwszy = j.aktualna
    _mig.przelicz_aktualna(global_apps, None)
    j.refresh_from_db()
    assert j.aktualna == pierwszy is True


# ---------------------------------------------------------------------------
# Ujednolicony sygnał: brak wpisów Jednostka_Rodzic → aktualna=True
# ---------------------------------------------------------------------------
@pytest.mark.django_db
def test_sygnal_brak_wpisow_true(uczelnia):
    """Po ujednoliceniu sygnał na dodaniu+usunięciu wpisu (koniec bez wpisów)
    daje ``aktualna=True`` (dawniej interim → False)."""
    j = _jednostka(uczelnia)
    wpis = baker.make(Jednostka_Rodzic, jednostka=j, parent=None, od=DAWNO, do=None)
    j.refresh_from_db()
    assert j.aktualna is True  # do IS NULL → True

    # Usuń wpis → sygnał post_delete → brak wpisów → True (nie False!)
    wpis.delete()
    j.refresh_from_db()
    assert j.aktualna is True


@pytest.mark.django_db
def test_sygnal_do_przeszlosc_false(uczelnia):
    j = _jednostka(uczelnia)
    baker.make(Jednostka_Rodzic, jednostka=j, parent=None, od=DAWNO, do=PRZESZLOSC)
    j.refresh_from_db()
    assert j.aktualna is False
