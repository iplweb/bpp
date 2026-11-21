from datetime import timedelta

import pytest
from django.utils import timezone
from model_bakery import baker

from pbn_export_queue.models import PBN_Export_Queue
from pbn_export_queue.tasks import queue_watchdog


@pytest.fixture
def delay(mocker):
    return mocker.patch("pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn").delay


def _wpis(rekord, **kw):
    kw.setdefault("wysylke_zakonczono", None)
    kw.setdefault("wykluczone", False)
    return baker.make(PBN_Export_Queue, rekord_do_wysylki=rekord, **kw)


@pytest.mark.django_db
def test_queue_watchdog_budzi_nigdy_niepodjety_wpis_z_domyslnym_none(
    wydawnictwo_ciagle, delay
):
    # Freshly queued entry: retry_after_user_authorised has its default None.
    wpis = _wpis(wydawnictwo_ciagle, wysylke_podjeto=None)
    assert wpis.retry_after_user_authorised is None

    assert queue_watchdog() == 1
    delay.assert_called_once_with(wpis.pk)


@pytest.mark.django_db
def test_queue_watchdog_budzi_utkniety_retry_z_none(wydawnictwo_ciagle, delay):
    wpis = _wpis(
        wydawnictwo_ciagle,
        wysylke_podjeto=timezone.now() - timedelta(hours=5),
    )
    assert wpis.retry_after_user_authorised is None

    assert queue_watchdog() == 1
    delay.assert_called_once_with(wpis.pk)


@pytest.mark.django_db
@pytest.mark.parametrize("podjeto_godzin_temu", [None, 5])
def test_queue_watchdog_pomija_wpisy_czekajace_na_autoryzacje(
    wydawnictwo_ciagle, delay, podjeto_godzin_temu
):
    podjeto = (
        None
        if podjeto_godzin_temu is None
        else timezone.now() - timedelta(hours=podjeto_godzin_temu)
    )
    _wpis(
        wydawnictwo_ciagle,
        wysylke_podjeto=podjeto,
        retry_after_user_authorised=True,
    )

    assert queue_watchdog() == 0
    delay.assert_not_called()


@pytest.mark.django_db
def test_queue_watchdog_pomija_swiezo_podjety_wpis(wydawnictwo_ciagle, delay):
    _wpis(wydawnictwo_ciagle, wysylke_podjeto=timezone.now())

    assert queue_watchdog() == 0
    delay.assert_not_called()
