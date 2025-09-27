from unittest.mock import MagicMock

import pytest
from model_bakery import baker

from pbn_export_queue.models import PBN_Export_Queue, SendStatus
from pbn_export_queue.tasks import (
    kolejka_ponow_wysylke_prac_po_zalogowaniu,
    kolejka_wyczysc_wpisy_bez_rekordow,
    task_sprobuj_wyslac_do_pbn,
)

from django.contrib.contenttypes.models import ContentType

from bpp.models import Wydawnictwo_Ciagle


@pytest.mark.django_db(transaction=True)
def test_kolejka_wyczysc_wpisy_bez_rekordow():
    # Jeżeli NIE damy content_type i nie wpiszemy klasy, to losowo dostaniemy klase np bpp.cache.Autorzy
    # albo bpp.cache.Rekord, a tam klucz jest złożony i będzie, że nie może castnąć int do int[],
    # albo dostaniemy tabelę cache temporary (cpaq)
    baker.make(
        PBN_Export_Queue,
        object_id=0xBEEF,
        content_type=ContentType.objects.get_for_model(Wydawnictwo_Ciagle),
    )
    assert PBN_Export_Queue.objects.count() == 1
    kolejka_wyczysc_wpisy_bez_rekordow()
    assert PBN_Export_Queue.objects.count() == 0


@pytest.mark.django_db(transaction=True)
def test_kolejka_wyczysc_wpisy_bez_rekordow_missing_table():
    """Test that the function handles missing database tables gracefully."""
    from bpp.models.cache.punktacja import Cache_Punktacja_Autora_Sum

    # Use ContentType for Cache_Punktacja_Autora_Sum which uses temporary table
    content_type = ContentType.objects.get_for_model(Cache_Punktacja_Autora_Sum)

    # Create a PBN_Export_Queue entry pointing to the temporary table that doesn't exist
    baker.make(PBN_Export_Queue, object_id=0xBEEF, content_type=content_type)
    assert PBN_Export_Queue.objects.count() == 1

    # This should handle the missing table gracefully and delete the orphaned record
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
        "pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn"
    )

    kolejka_ponow_wysylke_prac_po_zalogowaniu(peq.zamowil.pk)

    task_sprobuj_wyslac_do_pbn.delay.assert_called_once()


@pytest.mark.parametrize(
    "send_status",
    [SendStatus.RETRY_MUCH_LATER, SendStatus.RETRY_SOON, SendStatus.RETRY_LATER],
)
def test_task_sprobuj_wyslac_do_pbn_retry_later(mocker, send_status):
    task_sprobuj_wyslac_do_pbn_apply_async = mocker.patch(
        "pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn.apply_async"
    )

    wait_for_object = mocker.patch("pbn_export_queue.tasks.wait_for_object")

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
    mocker.patch("pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn.apply_async")

    wait_for_object = mocker.patch("pbn_export_queue.tasks.wait_for_object")

    mock_peq = MagicMock()
    mock_peq.send_to_pbn.return_value = send_status

    wait_for_object.return_value = mock_peq

    task_sprobuj_wyslac_do_pbn(5)


def test_task_sprobuj_wyslac_do_pbn_raises(mocker):
    wait_for_object = mocker.patch("pbn_export_queue.tasks.wait_for_object")

    mock_peq = MagicMock()
    mock_peq.send_to_pbn.side_return_value = 0xBEEF

    wait_for_object.return_value = mock_peq

    with pytest.raises(NotImplementedError):
        task_sprobuj_wyslac_do_pbn(5)
