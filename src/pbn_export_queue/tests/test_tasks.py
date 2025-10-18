from unittest.mock import MagicMock

import pytest
from model_bakery import baker

from pbn_export_queue.models import PBN_Export_Queue, SendStatus
from pbn_export_queue.tasks import (
    kolejka_ponow_wysylke_prac_po_zalogowaniu,
    kolejka_wyczysc_wpisy_bez_rekordow,
    queue_pbn_export_batch,
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
@pytest.mark.django_db
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


@pytest.mark.django_db
def test_kolejka_ponow_wysylke_prac_po_zalogowaniu_with_other_users(
    wydawnictwo_ciagle, mocker
):
    """Test that task resends items for users with shared PBN account"""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    # Create two users - one is the PBN account owner
    pbn_user = baker.make(User, username="pbn_account_owner")
    delegated_user = baker.make(User, username="delegated_user")

    # Make delegated_user represent pbn_user in PBN
    delegated_user.przedstawiaj_w_pbn_jako = pbn_user
    delegated_user.save()

    # Create queue item for delegated user
    peq = baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=wydawnictwo_ciagle,
        zamowil=delegated_user,
        retry_after_user_authorised=True,
        wysylke_zakonczono=None,
    )

    task_sprobuj_wyslac_do_pbn = mocker.patch(
        "pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn"
    )

    # Call the task with pbn_user's ID
    kolejka_ponow_wysylke_prac_po_zalogowaniu(pbn_user.pk)

    # Check that task was called for delegated user's item
    task_sprobuj_wyslac_do_pbn.delay.assert_called()


@pytest.mark.django_db(transaction=True)
def test_queue_pbn_export_batch(mocker):
    """Test batch queueing of PBN exports."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    # Create a test user
    user = User.objects.create_user(username="test_user", password="testpass")

    # Create multiple wydawnictwo_ciagle records
    record1 = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Test Record 1",
    )
    record2 = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Test Record 2",
    )
    record3 = baker.make(
        Wydawnictwo_Ciagle,
        tytul_oryginalny="Test Record 3",
    )

    # Mock the task_sprobuj_wyslac_do_pbn.delay to track calls
    mock_task_delay = mocker.patch(
        "pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn.delay"
    )

    # Collect record IDs
    record_ids = [record1.id, record2.id, record3.id]

    # Call the batch export task
    queue_pbn_export_batch(
        app_label="bpp",
        model_name="wydawnictwo_ciagle",
        record_ids=record_ids,
        user_id=user.id,
    )

    # Verify that all records were added to queue
    assert PBN_Export_Queue.objects.count() == 3

    # Verify that all queue entries have correct user
    queue_entries = PBN_Export_Queue.objects.all()
    for entry in queue_entries:
        assert entry.zamowil == user

    # Verify that task_sprobuj_wyslac_do_pbn was called for each record
    assert mock_task_delay.call_count == 3


@pytest.mark.django_db(transaction=True)
def test_queue_pbn_export_batch_skips_duplicates(mocker):
    """Test that batch queueing skips records already in queue."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(username="test_user", password="testpass")

    # Create a record
    record = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Test Record")

    # Add it to queue once
    baker.make(
        PBN_Export_Queue,
        rekord_do_wysylki=record,
        zamowil=user,
        wysylke_zakonczono=None,
    )

    # Mock the task
    mock_task_delay = mocker.patch(
        "pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn.delay"
    )

    # Try to add same record again
    queue_pbn_export_batch(
        app_label="bpp",
        model_name="wydawnictwo_ciagle",
        record_ids=[record.id],
        user_id=user.id,
    )

    # Should still be only 1 in queue (no duplicate added)
    assert PBN_Export_Queue.objects.count() == 1

    # task should not be called (AlreadyEnqueuedError)
    mock_task_delay.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_queue_pbn_export_batch_invalid_user(mocker):
    """Test batch queueing with non-existent user."""
    # Mock the task
    mock_task_delay = mocker.patch(
        "pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn.delay"
    )

    record = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="Test Record")

    # Call with non-existent user ID
    queue_pbn_export_batch(
        app_label="bpp",
        model_name="wydawnictwo_ciagle",
        record_ids=[record.id],
        user_id=99999,  # Non-existent user
    )

    # Nothing should be added to queue
    assert PBN_Export_Queue.objects.count() == 0
    mock_task_delay.assert_not_called()


@pytest.mark.django_db(transaction=True)
def test_queue_pbn_export_batch_invalid_records(mocker):
    """Test batch queueing with non-existent records."""
    from django.contrib.auth import get_user_model

    User = get_user_model()
    user = User.objects.create_user(username="test_user2", password="testpass")

    # Mock the task
    mock_task_delay = mocker.patch(
        "pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn.delay"
    )

    # Call with non-existent record IDs
    queue_pbn_export_batch(
        app_label="bpp",
        model_name="wydawnictwo_ciagle",
        record_ids=[99999, 88888],  # Non-existent records
        user_id=user.id,
    )

    # Nothing should be added to queue
    assert PBN_Export_Queue.objects.count() == 0
    mock_task_delay.assert_not_called()
