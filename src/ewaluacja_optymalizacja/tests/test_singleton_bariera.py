"""Testy bariery bazodanowej dla dwóch najgroźniejszych zadań singletonów.

``optimize_and_unpin_task`` i ``unpin_all_sensible_task`` masowo odpinają
przypięcia całej uczelni. Lock ``celery_singleton`` (Redis) to pierwsza
warstwa, ale ``clear_locks`` na sygnale ``worker_ready`` kasuje go przy
restarcie DOWOLNEGO workera — przy wielu kontenerach rolling restart zwalnia
lock chroniący przebieg trwający gdzie indziej. Tu testujemy drugą,
niezależną od Redisa warstwę: classmethody ``sprobuj_zajac_slot`` osadzone na
singletonach statusu (wzorzec #629, ``_przejmij_slot_skanu``).
"""

import threading
from datetime import timedelta

import pytest
from django.db import connections
from django.utils import timezone

from ewaluacja_optymalizacja.models import (
    StatusOdpinaniaWszystkich,
    StatusOptymalizacjiZOdpinaniem,
)

# Oba modele mają identyczny kontrakt bariery — testy współdzielone lecą po obu.
MODELE = [StatusOptymalizacjiZOdpinaniem, StatusOdpinaniaWszystkich]


def _prime(model, task_id, wiek_sekund=0):
    """Ustaw singleton w stan RUNNING pod danym ``task_id``, postarzony."""
    obj = model.get_or_create()
    obj.w_trakcie = True
    obj.task_id = task_id
    obj.data_rozpoczecia = timezone.now() - timedelta(seconds=wiek_sekund)
    obj.data_zakonczenia = None
    obj.save()
    return obj


@pytest.mark.django_db
@pytest.mark.parametrize("model", MODELE)
def test_slot_wolny_gdy_brak_stanu(model):
    """Pusty singleton: slot się zajmuje i ustawia w_trakcie=True."""
    assert model.sprobuj_zajac_slot("abc") is True

    obj = model.get_or_create()
    assert obj.w_trakcie is True
    assert obj.task_id == "abc"
    assert obj.data_rozpoczecia is not None


@pytest.mark.django_db
@pytest.mark.parametrize("model", MODELE)
def test_moj_task_id_nie_blokuje_sam_siebie(model):
    """Widok ustawia w_trakcie z task_id zadania PRZED jego startem.

    Bariera na wejściu do tego samego zadania musi rozpoznać „to ja" i
    przepuścić — inaczej pierwszy legalny przebieg fałszywie by się wycofał.
    """
    _prime(model, "ten-sam-task", wiek_sekund=5)

    assert model.sprobuj_zajac_slot("ten-sam-task") is True


@pytest.mark.django_db
@pytest.mark.parametrize("model", MODELE)
def test_obcy_swiezy_przebieg_blokuje(model):
    """Świeży przebieg pod INNYM task_id blokuje — druga próba dostaje False."""
    _prime(model, "pierwszy", wiek_sekund=10)

    assert model.sprobuj_zajac_slot("drugi") is False

    # Stan pierwszego przebiegu nietknięty.
    obj = model.get_or_create()
    assert obj.w_trakcie is True
    assert obj.task_id == "pierwszy"


@pytest.mark.django_db
@pytest.mark.parametrize("model", MODELE)
def test_zombie_jest_przejmowany(model):
    """RUNNING starszy niż próg = zombie po ubitym workerze: slot przejmuje
    nowy przebieg (brak zakleszczenia na zawsze)."""
    _prime(model, "stary", wiek_sekund=model.BARIERA_STALE_AFTER + 60)

    assert model.sprobuj_zajac_slot("nowy") is True

    obj = model.get_or_create()
    assert obj.task_id == "nowy"
    assert obj.w_trakcie is True


@pytest.mark.django_db
@pytest.mark.parametrize("model", MODELE)
def test_swiezy_tuz_przed_progiem_nadal_blokuje(model):
    """Granica: wpis MŁODSZY niż próg to wciąż żywy przebieg."""
    _prime(model, "pierwszy", wiek_sekund=model.BARIERA_STALE_AFTER - 60)

    assert model.sprobuj_zajac_slot("drugi") is False


@pytest.mark.django_db
@pytest.mark.parametrize("model", MODELE)
def test_zakonczony_przebieg_nie_blokuje(model):
    """w_trakcie=False (zakończony) nie blokuje kolejnego uruchomienia."""
    obj = model.get_or_create()
    obj.w_trakcie = False
    obj.task_id = "poprzedni"
    obj.data_rozpoczecia = timezone.now()
    obj.save()

    assert model.sprobuj_zajac_slot("nowy") is True


@pytest.mark.django_db
def test_zwolnij_slot_tylko_gdy_wciaz_nasz():
    """zwolnij_slot zdejmuje w_trakcie tylko dla pasującego task_id.

    Gdy nasz wpis przejął już nowszy przebieg (inny task_id), nasze
    ``finally`` nie może mu skasować w_trakcie."""
    _prime(StatusOdpinaniaWszystkich, "moj", wiek_sekund=5)

    # Nie nasz task_id — brak zmiany.
    StatusOdpinaniaWszystkich.zwolnij_slot("ktos-inny")
    assert StatusOdpinaniaWszystkich.get_or_create().w_trakcie is True

    # Nasz task_id — zwolnione.
    StatusOdpinaniaWszystkich.zwolnij_slot("moj")
    obj = StatusOdpinaniaWszystkich.get_or_create()
    assert obj.w_trakcie is False
    assert obj.data_zakonczenia is not None


@pytest.mark.django_db
def test_lock_id_stale_literaly():
    """Klucze advisory locków to zapieczone literały (nie hash() solony
    PYTHONHASHSEED). Zmiana wartości = mieszany deployment przestaje
    wykluczać, więc pilnujemy jej testem."""
    assert StatusOptymalizacjiZOdpinaniem.BARIERA_LOCK_ID == 1837898708916349040
    assert StatusOdpinaniaWszystkich.BARIERA_LOCK_ID == 4628564544925194477
    # Oba klucze różne — nie blokują się nawzajem w jedno-arg. przestrzeni.
    assert (
        StatusOptymalizacjiZOdpinaniem.BARIERA_LOCK_ID
        != StatusOdpinaniaWszystkich.BARIERA_LOCK_ID
    )


LICZBA_WATKOW = 8


@pytest.mark.django_db(transaction=True)
def test_wspolbieznie_tylko_jeden_przejmuje_slot():
    """N wątków startujących RÓWNOCZEŚNIE z pustego singletona: dokładnie
    jeden dostaje slot.

    Ten test łapie regresję, gdyby ktoś wrócił do ``select_for_update``
    (nieatomowego na pustym/False'owym zbiorze) albo usunął advisory lock.
    """
    model = StatusOdpinaniaWszystkich
    assert model.get_or_create().w_trakcie is False

    start = threading.Barrier(LICZBA_WATKOW)
    wyniki = [None] * LICZBA_WATKOW
    bledy = [None] * LICZBA_WATKOW

    def worker(idx):
        try:
            start.wait(timeout=30)
            wyniki[idx] = model.sprobuj_zajac_slot(f"t{idx}")
        except Exception as exc:  # noqa: BLE001 - re-raise'owane po joinie
            bledy[idx] = exc
        finally:
            connections.close_all()

    watki = [threading.Thread(target=worker, args=(i,)) for i in range(LICZBA_WATKOW)]
    for w in watki:
        w.start()
    for w in watki:
        w.join(timeout=60)

    for idx, blad in enumerate(bledy):
        assert blad is None, f"wątek {idx} wywalił się: {blad!r}"

    przyznane = sum(1 for w in wyniki if w)
    assert przyznane == 1, (
        f"slot przejęło {przyznane} z {LICZBA_WATKOW} wątków — bariera nie jest atomowa"
    )
