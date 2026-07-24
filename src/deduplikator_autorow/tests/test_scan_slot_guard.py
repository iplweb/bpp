"""Testy bariery bazodanowej chroniącej przed równoległymi skanami.

Lock `GlobalSingleton` (Redis) to pierwsza warstwa, ale `clear_locks` na
sygnale `worker_ready` kasuje go przy restarcie DOWOLNEGO workera — przy
wielu kontenerach rolling restart zwalnia lock chroniący przebieg trwający
gdzie indziej. Tu testujemy drugą, niezależną warstwę: `_przejmij_slot_skanu`.
"""

from datetime import timedelta

import pytest
from django.utils import timezone
from model_bakery import baker

from deduplikator_autorow.models import DuplicateCandidate, DuplicateScanRun
from deduplikator_autorow.tasks import (
    SCAN_STALE_AFTER,
    _przejmij_slot_skanu,
    scan_for_duplicates,
)


def _scan_run(status, wiek_sekund=0):
    """DuplicateScanRun o zadanym statusie, postarzony o `wiek_sekund`."""
    run = DuplicateScanRun.objects.create(status=status)
    if wiek_sekund:
        DuplicateScanRun.objects.filter(pk=run.pk).update(
            started_at=timezone.now() - timedelta(seconds=wiek_sekund)
        )
        run.refresh_from_db()
    return run


@pytest.mark.django_db
def test_slot_wolny_gdy_brak_trwajacych():
    """Bez trwających przebiegów slot się zajmuje i wraca nowy scan run."""
    scan_run = _przejmij_slot_skanu(user=None, celery_task_id="abc")

    assert scan_run is not None
    assert scan_run.status == DuplicateScanRun.Status.RUNNING
    assert scan_run.celery_task_id == "abc"


@pytest.mark.django_db
def test_slot_zajety_gdy_trwa_swiezy_skan():
    """Świeży RUNNING blokuje — druga próba dostaje None."""
    trwajacy = _scan_run(DuplicateScanRun.Status.RUNNING)

    assert _przejmij_slot_skanu(user=None, celery_task_id="drugi") is None

    # Nie powstał żaden nowy wpis; trwający nietknięty.
    assert DuplicateScanRun.objects.count() == 1
    trwajacy.refresh_from_db()
    assert trwajacy.status == DuplicateScanRun.Status.RUNNING


@pytest.mark.django_db
def test_osierocony_running_jest_przeterminowany():
    """RUNNING starszy niż SCAN_STALE_AFTER = zombie po ubitym workerze:
    przechodzi na FAILED, a slot zostaje zwolniony (brak zakleszczenia)."""
    zombie = _scan_run(
        DuplicateScanRun.Status.RUNNING, wiek_sekund=SCAN_STALE_AFTER + 60
    )

    scan_run = _przejmij_slot_skanu(user=None, celery_task_id="nowy")

    assert scan_run is not None, "osierocony wpis nie może blokować na zawsze"
    zombie.refresh_from_db()
    assert zombie.status == DuplicateScanRun.Status.FAILED
    assert zombie.finished_at is not None
    assert "porzucony" in zombie.error_message


@pytest.mark.django_db
def test_swiezy_running_tuz_przed_progiem_nadal_blokuje():
    """Granica: wpis MŁODSZY niż próg to wciąż żywy przebieg."""
    _scan_run(DuplicateScanRun.Status.RUNNING, wiek_sekund=SCAN_STALE_AFTER - 60)

    assert _przejmij_slot_skanu(user=None, celery_task_id="drugi") is None


@pytest.mark.django_db
@pytest.mark.parametrize(
    "status",
    [
        DuplicateScanRun.Status.COMPLETED,
        DuplicateScanRun.Status.FAILED,
        DuplicateScanRun.Status.CANCELLED,
        DuplicateScanRun.Status.PARTIAL_COMPLETED,
    ],
)
def test_zakonczone_przebiegi_nie_blokuja(status):
    """Tylko RUNNING blokuje — statusy końcowe są bez znaczenia."""
    _scan_run(status)

    assert _przejmij_slot_skanu(user=None, celery_task_id="nowy") is not None


@pytest.mark.django_db
def test_zadanie_nie_kasuje_kandydatow_gdy_skan_juz_trwa():
    """NAJWAŻNIEJSZE: przy trwającym skanie zadanie wycofuje się ZANIM
    wykona `DuplicateCandidate.objects.all().delete()`.

    To jest dokładnie ta szkoda, przed którą broni bariera — bez niej drugi
    przebieg (wpuszczony po `clear_locks` na restarcie workera) skasowałby
    wyniki pierwszego."""
    _scan_run(DuplicateScanRun.Status.RUNNING)

    a1 = baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    a2 = baker.make("bpp.Autor", nazwisko="Kowalski", imiona="Jan")
    kandydat = baker.make(DuplicateCandidate, main_autor=a1, duplicate_autor=a2)

    result = scan_for_duplicates.apply().result

    assert result["status"] == "already_running"
    # Kandydat przeżył — nic nie zostało skasowane.
    assert DuplicateCandidate.objects.filter(pk=kandydat.pk).exists()
