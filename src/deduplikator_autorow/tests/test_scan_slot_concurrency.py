"""Test WSPÓŁBIEŻNOŚCI bariery slotu skanu duplikatów.

Osobny plik od `test_scan_slot_guard.py`, bo wymaga `django_db(transaction=True)`
(prawdziwe commity, wiele połączeń), co jest istotnie wolniejsze niż domyślny
tryb owinięty w transakcję.

DLACZEGO to musi istnieć: wszystkie testy sekwencyjne przechodziły również na
implementacji opartej o `select_for_update`, która NIE była atomowa —
`SELECT ... FOR UPDATE` blokuje znalezione wiersze, a przy braku trwającego
skanu zbiór jest pusty, więc nie blokuje niczego i N równoległych transakcji
tworzy N wpisów RUNNING (phantom read). Ten test odtwarza dokładnie ten
scenariusz i jest jedynym, który łapie regresję, gdyby ktoś wrócił do
`select_for_update` albo usunął advisory lock.
"""

import threading

import pytest
from django.db import connections

from deduplikator_autorow.models import DuplicateScanRun
from deduplikator_autorow.tasks import _przejmij_slot_skanu

LICZBA_WATKOW = 8


@pytest.mark.django_db(transaction=True)
def test_tylko_jeden_watek_przejmuje_slot_skanu():
    """N wątków startujących RÓWNOCZEŚNIE z pustej tabeli: dokładnie jeden
    dostaje slot i dokładnie jeden wiersz RUNNING ląduje w bazie.

    Bez tego zabezpieczenia każdy z tych wątków wszedłby w
    `DuplicateCandidate.objects.all().delete()`.
    """
    assert not DuplicateScanRun.objects.exists(), "test startuje z pustej tabeli"

    # Bariera zamiast sleepów: wszystkie wątki ruszają w tej samej chwili,
    # co maksymalizuje szansę na wyścig (sleep byłby i wolniejszy, i mniej
    # deterministyczny).
    start = threading.Barrier(LICZBA_WATKOW)
    wyniki = [None] * LICZBA_WATKOW
    bledy = [None] * LICZBA_WATKOW

    def worker(idx):
        try:
            start.wait(timeout=30)
            scan_run = _przejmij_slot_skanu(user=None, celery_task_id=f"t{idx}")
            wyniki[idx] = scan_run is not None
        except Exception as exc:  # noqa: BLE001 - re-raise'owane po joinie
            bledy[idx] = exc
        finally:
            # Każdy wątek dostaje własne połączenie — musi je zamknąć, inaczej
            # zostaje otwarte i teardown bazy się zawiesza.
            connections.close_all()

    watki = [threading.Thread(target=worker, args=(i,)) for i in range(LICZBA_WATKOW)]
    for w in watki:
        w.start()
    for w in watki:
        w.join(timeout=60)

    for idx, blad in enumerate(bledy):
        assert blad is None, f"wątek {idx} wywalił się: {blad!r}"

    przyznane = sum(1 for w in wyniki if w)
    running_w_bazie = DuplicateScanRun.objects.filter(
        status=DuplicateScanRun.Status.RUNNING
    ).count()

    assert przyznane == 1, (
        f"slot przejęło {przyznane} z {LICZBA_WATKOW} wątków — bariera nie jest atomowa"
    )
    assert running_w_bazie == 1, (
        f"w bazie {running_w_bazie} wierszy RUNNING zamiast 1 — "
        f"tyle równoległych przebiegów skasowałoby sobie nawzajem wyniki"
    )


@pytest.mark.django_db(transaction=True)
def test_wspolbieznie_tylko_jeden_przejmuje_slot_po_zombie():
    """Wariant z osieroconym wpisem: N wątków zastaje zombie RUNNING.

    Zombie ma zostać przeterminowany (dokładnie raz — nie N razy), a slot
    przejąć dokładnie jeden wątek.
    """
    from datetime import timedelta

    from django.utils import timezone

    from deduplikator_autorow.tasks import SCAN_STALE_AFTER

    zombie = DuplicateScanRun.objects.create(status=DuplicateScanRun.Status.RUNNING)
    DuplicateScanRun.objects.filter(pk=zombie.pk).update(
        started_at=timezone.now() - timedelta(seconds=SCAN_STALE_AFTER + 60)
    )

    start = threading.Barrier(LICZBA_WATKOW)
    wyniki = [None] * LICZBA_WATKOW
    bledy = [None] * LICZBA_WATKOW

    def worker(idx):
        try:
            start.wait(timeout=30)
            scan_run = _przejmij_slot_skanu(user=None, celery_task_id=f"z{idx}")
            wyniki[idx] = scan_run is not None
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

    assert sum(1 for w in wyniki if w) == 1
    zombie.refresh_from_db()
    assert zombie.status == DuplicateScanRun.Status.FAILED
    assert (
        DuplicateScanRun.objects.filter(status=DuplicateScanRun.Status.RUNNING).count()
        == 1
    )
