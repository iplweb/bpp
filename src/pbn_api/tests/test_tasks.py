from unittest.mock import MagicMock

import pytest
from model_bakery import baker

from pbn_api.models import PBN_Export_Queue
from pbn_api.models.queue import SendStatus
from pbn_api.tasks import (
    kolejka_ponow_wysylke_prac_po_zalogowaniu,
    kolejka_wyczysc_wpisy_bez_rekordow,
    task_sprobuj_wyslac_do_pbn,
)


@pytest.mark.django_db
def test_kolejka_wyczysc_wpisy_bez_rekordow():
    baker.make(PBN_Export_Queue, object_id=0xBEEF)
    assert PBN_Export_Queue.objects.count() == 1
    kolejka_wyczysc_wpisy_bez_rekordow()
    assert PBN_Export_Queue.objects.count() == 0


@pytest.mark.django_db
def test_kolejka_ponow_wysylke_prac_po_zalogowaniu(wydawnictwo_ciagle, mocker):
    peq = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        retry_after_user_authorised=True,
        wysylke_zakonczono=None,
    )

    task_sprobuj_wyslac_do_pbn = mocker.patch(
        "pbn_api.tasks.task_sprobuj_wyslac_do_pbn"
    )

    kolejka_ponow_wysylke_prac_po_zalogowaniu(peq.zamowil.pk)

    task_sprobuj_wyslac_do_pbn.delay.assert_called_once()


@pytest.mark.parametrize(
    "send_status",
    [SendStatus.RETRY_MUCH_LATER, SendStatus.RETRY_SOON, SendStatus.RETRY_LATER],
)
def test_task_sprobuj_wyslac_do_pbn_retry_later(mocker, send_status):
    task_sprobuj_wyslac_do_pbn_apply_async = mocker.patch(
        "pbn_api.tasks.task_sprobuj_wyslac_do_pbn.apply_async"
    )

    wait_for_object = mocker.patch("pbn_api.tasks.wait_for_object")

    mock_peq = MagicMock()
    mock_peq.send_to_pbn.return_value = send_status

    wait_for_object.return_value = mock_peq

    task_sprobuj_wyslac_do_pbn(5)

    # Upewnij się, ze zadanie jest uruchamiane ponownie, ale ciut później
    task_sprobuj_wyslac_do_pbn_apply_async.assert_called_once()


@pytest.mark.parametrize(
    "send_status",
    [
        SendStatus.FINISHED_ERROR,
        SendStatus.FINISHED_OKAY,
        SendStatus.RETRY_AFTER_USER_AUTHORISED,
    ],
)
def test_task_sprobuj_wyslac_do_pbn_finished(mocker, send_status):
    mocker.patch("pbn_api.tasks.task_sprobuj_wyslac_do_pbn.apply_async")

    wait_for_object = mocker.patch("pbn_api.tasks.wait_for_object")

    mock_peq = MagicMock()
    mock_peq.send_to_pbn.return_value = send_status

    wait_for_object.return_value = mock_peq

    task_sprobuj_wyslac_do_pbn(5)


def test_task_sprobuj_wyslac_do_pbn_raises(mocker):
    wait_for_object = mocker.patch("pbn_api.tasks.wait_for_object")

    mock_peq = MagicMock()
    mock_peq.send_to_pbn.side_return_value = 0xBEEF

    wait_for_object.return_value = mock_peq

    with pytest.raises(NotImplementedError):
        task_sprobuj_wyslac_do_pbn(5)
