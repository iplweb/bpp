"""Audyt poz. 1.5 — lost update na singletonach statusu (``pk=1``).

Metody ``rozpocznij()``/``zakoncz()`` modeli ``Status*`` wcześniej
zapisywały **cały** wiersz przez ``save()``. Ładowały obiekt (kopię w
Pythonie), mutowały kilka pól i nadpisywały wszystkie kolumny — w tym te,
których operacja logicznie NIE dotyczy (``task_id``, ``data_rozpoczecia``,
``uczelnia``, ``punkty_przed``). Gdy inne, współbieżne zadanie w międzyczasie
zmieniło jedno z tych pól, stary zapis je **gubił** (last-write-wins).

Po naprawie ``zakoncz()`` zapisuje tylko pola, które faktycznie zmienia
(``w_trakcie``, ``data_zakonczenia``, ``ostatni_komunikat``), więc
współbieżna zmiana ``task_id`` przetrwa.

Testy:
- ``test_zakoncz_nie_gubi_wspolbieznej_zmiany_task_id`` — dowód naprawy.
- ``test_stara_implementacja_calego_wiersza_gubilaby_task_id`` — test
  kontrolny (reguła #8): stara ścieżka ``save()`` całego wiersza faktycznie
  gubi współbieżną zmianę ``task_id``.
- ``test_zakoncz_ustawia_timestamp_jawnie`` — dowód, że brak ``auto_now``
  nie regresuje: ``data_zakonczenia`` nadal jest ustawiany.
"""

import pytest
from django.utils import timezone

from ewaluacja_optymalizacja.models.status import (
    StatusOptymalizacjiZOdpinaniem,
)


@pytest.mark.django_db(transaction=True)
def test_zakoncz_nie_gubi_wspolbieznej_zmiany_task_id():
    """Po naprawie: ``zakoncz()`` nie nadpisuje współbieżnie zmienionego
    ``task_id``, bo zapisuje tylko własne pola."""
    status = StatusOptymalizacjiZOdpinaniem.get_or_create()
    status.rozpocznij(task_id="TASK-ORIGINAL")

    # Załaduj drugą, niezależną kopię tego samego wiersza (symulacja
    # drugiego procesu/requestu, który wystartował z tego samego stanu).
    stale = StatusOptymalizacjiZOdpinaniem.objects.get(pk=1)

    # Współbieżnie (inny proces) podmienia task_id w bazie.
    StatusOptymalizacjiZOdpinaniem.objects.filter(pk=1).update(
        task_id="TASK-CONCURRENT"
    )

    # Ta kopia, nieświadoma zmiany, kończy zadanie.
    stale.zakoncz("Zakończono")

    fresh = StatusOptymalizacjiZOdpinaniem.objects.get(pk=1)
    # Współbieżny task_id NIE zginął:
    assert fresh.task_id == "TASK-CONCURRENT"
    # A pola, które zakoncz() faktycznie zmienia, są zapisane:
    assert fresh.w_trakcie is False
    assert fresh.ostatni_komunikat == "Zakończono"
    assert fresh.data_zakonczenia is not None


@pytest.mark.django_db(transaction=True)
def test_stara_implementacja_calego_wiersza_gubilaby_task_id():
    """Test kontrolny: stara implementacja (``save()`` całego wiersza)
    zgubiłaby współbieżną zmianę ``task_id``. Odtwarzamy tu jej zachowanie
    ręcznie, żeby udowodnić, że powyższy test naprawy testuje realny problem,
    a nie tautologię."""
    status = StatusOptymalizacjiZOdpinaniem.get_or_create()
    status.rozpocznij(task_id="TASK-ORIGINAL")

    stale = StatusOptymalizacjiZOdpinaniem.objects.get(pk=1)

    StatusOptymalizacjiZOdpinaniem.objects.filter(pk=1).update(
        task_id="TASK-CONCURRENT"
    )

    # STARE zachowanie zakoncz(): mutacja + save() CAŁEGO wiersza.
    stale.w_trakcie = False
    stale.data_zakonczenia = timezone.now()
    stale.ostatni_komunikat = "Zakończono"
    stale.save()  # nadpisuje wszystkie kolumny stanem sprzed współbieżnej zmiany

    fresh = StatusOptymalizacjiZOdpinaniem.objects.get(pk=1)
    # Stary kod gubi współbieżny task_id — cofa go do wartości z kopii:
    assert fresh.task_id == "TASK-ORIGINAL"


@pytest.mark.django_db(transaction=True)
def test_zakoncz_ustawia_timestamp_jawnie():
    """Brak ``auto_now`` na modelu → ``.update()`` nie odświeżyłby żadnego
    timestampu automatycznie. Dowód, że ``data_zakonczenia`` jest ustawiany
    jawnie i naprawa nie regresuje tego zachowania."""
    status = StatusOptymalizacjiZOdpinaniem.get_or_create()
    status.rozpocznij(task_id="T1")
    assert StatusOptymalizacjiZOdpinaniem.objects.get(pk=1).data_zakonczenia is None

    before = timezone.now()
    status.zakoncz("Gotowe")
    after = timezone.now()

    fresh = StatusOptymalizacjiZOdpinaniem.objects.get(pk=1)
    assert fresh.data_zakonczenia is not None
    assert before <= fresh.data_zakonczenia <= after
    # In-memory instancja także zaktualizowana (zachowanie jak przy save()):
    assert status.data_zakonczenia is not None


@pytest.mark.django_db(transaction=True)
def test_rozpocznij_zapisuje_wlasne_pola():
    """``rozpocznij()`` po naprawie nadal poprawnie ustawia swój zestaw pól
    (w bazie i w instancji)."""
    status = StatusOptymalizacjiZOdpinaniem.get_or_create()
    status.zakoncz("stan poczatkowy")

    status.rozpocznij(task_id="NOWE-ZADANIE")

    fresh = StatusOptymalizacjiZOdpinaniem.objects.get(pk=1)
    assert fresh.w_trakcie is True
    assert fresh.task_id == "NOWE-ZADANIE"
    assert fresh.data_rozpoczecia is not None
    assert fresh.data_zakonczenia is None
    assert fresh.ostatni_komunikat == "Rozpoczęto optymalizację z odpinaniem"
