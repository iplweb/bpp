"""Test WSPÓŁBIEŻNOŚCI: advisory lock wysyłki oświadczeń naprawdę wyklucza.

Wzorzec z `deduplikator_autorow/tests/test_scan_slot_concurrency.py`:
`django_db(transaction=True)` (prawdziwe commity, osobne połączenia per
wątek) + `threading.Barrier`, żeby wszystkie wątki ruszyły w tej samej
chwili.

DLACZEGO to musi istnieć: sam fakt, że klucz jest deterministyczny, nie
dowodzi, że sekcja krytyczna jest faktycznie serializowana. Ten test
sprawdza obserwowalny skutek — z N wątków wchodzących równocześnie
dokładnie JEDEN widzi pustą tabelę i tworzy zadanie. Gdyby klucz był
liczony per proces/wątek (albo lock zniknął), przeszłoby ich N i do PBN
poleciałaby zduplikowana wysyłka oświadczeń.
"""

import threading

import pytest
from django.db import connection, connections, transaction

from django_bpp.db_locks import advisory_lock_id
from pbn_wysylka_oswiadczen.models import PbnWysylkaOswiadczenTask

LICZBA_WATKOW = 8

LOCK_KEY = advisory_lock_id("pbn_wysylka_oswiadczen.views.PbnWysylkaOswiadczenTask")


def _sprobuj_zajac_slot(user_id):
    """Odwzorowuje sekcję krytyczną z `views.py` (lock + exists + create)."""
    with transaction.atomic():
        with connection.cursor() as cursor:
            cursor.execute("SELECT pg_advisory_xact_lock(%s)", [LOCK_KEY])

        if PbnWysylkaOswiadczenTask.objects.filter(
            status__in=("pending", "running")
        ).exists():
            return False

        PbnWysylkaOswiadczenTask.objects.create(user_id=user_id, status="pending")
        return True


@pytest.mark.django_db(transaction=True)
def test_tylko_jeden_watek_zaklada_zadanie_wysylki(django_user_model):
    assert not PbnWysylkaOswiadczenTask.objects.exists(), "start z pustej tabeli"

    user = django_user_model.objects.create_user(username="lock-test")

    start = threading.Barrier(LICZBA_WATKOW)
    wyniki = [None] * LICZBA_WATKOW
    bledy = [None] * LICZBA_WATKOW

    def worker(idx):
        try:
            start.wait(timeout=30)
            wyniki[idx] = _sprobuj_zajac_slot(user.pk)
        except Exception as exc:  # noqa: BLE001 - re-raise'owane po joinie
            bledy[idx] = exc
        finally:
            # Każdy wątek ma własne połączenie; bez zamknięcia teardown
            # bazy się zawiesza.
            connections.close_all()

    watki = [threading.Thread(target=worker, args=(i,)) for i in range(LICZBA_WATKOW)]
    for w in watki:
        w.start()
    for w in watki:
        w.join(timeout=60)

    for blad in bledy:
        if blad is not None:
            raise blad

    assert sum(1 for w in wyniki if w) == 1, f"więcej niż jeden zwycięzca: {wyniki}"
    assert PbnWysylkaOswiadczenTask.objects.count() == 1
