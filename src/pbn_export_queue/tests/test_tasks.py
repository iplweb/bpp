from unittest.mock import MagicMock

import pytest
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from model_bakery import baker

from bpp.models import Wydawnictwo_Ciagle
from pbn_export_queue.models import PBN_Export_Queue, RodzajBledu, SendStatus
from pbn_export_queue.tasks import (
    kolejka_ponow_wysylke_prac_po_zalogowaniu,
    kolejka_wyczysc_wpisy_bez_rekordow,
    queue_pbn_export_batch,
    report_technical_errors_to_rollbar,
    task_sprobuj_wyslac_do_pbn,
)


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
    # Mock cache operations
    mock_cache_add = mocker.patch("pbn_export_queue.tasks.cache.add", return_value=True)
    mock_cache_delete = mocker.patch("pbn_export_queue.tasks.cache.delete")

    task_sprobuj_wyslac_do_pbn_apply_async = mocker.patch(
        "pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn.apply_async"
    )

    wait_for_object = mocker.patch("pbn_export_queue.tasks.wait_for_object")

    mock_peq = MagicMock()
    mock_peq.send_to_pbn.return_value = send_status
    mock_peq.wysylke_zakonczono = None

    wait_for_object.return_value = mock_peq

    task_sprobuj_wyslac_do_pbn(5)

    # Check that lock was acquired and released
    mock_cache_add.assert_called_once()
    mock_cache_delete.assert_called_once()

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
    # Mock cache operations
    mock_cache_add = mocker.patch("pbn_export_queue.tasks.cache.add", return_value=True)
    mock_cache_delete = mocker.patch("pbn_export_queue.tasks.cache.delete")

    mocker.patch("pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn.apply_async")

    wait_for_object = mocker.patch("pbn_export_queue.tasks.wait_for_object")

    mock_peq = MagicMock()
    mock_peq.send_to_pbn.return_value = send_status
    mock_peq.wysylke_zakonczono = None

    wait_for_object.return_value = mock_peq

    task_sprobuj_wyslac_do_pbn(5)

    # Check that lock was acquired and released
    mock_cache_add.assert_called_once()
    mock_cache_delete.assert_called_once()


def test_task_sprobuj_wyslac_do_pbn_raises(mocker):
    # Mock cache operations
    mock_cache_add = mocker.patch("pbn_export_queue.tasks.cache.add", return_value=True)
    mock_cache_delete = mocker.patch("pbn_export_queue.tasks.cache.delete")

    wait_for_object = mocker.patch("pbn_export_queue.tasks.wait_for_object")

    mock_peq = MagicMock()
    mock_peq.send_to_pbn.return_value = 0xBEEF  # Invalid status
    mock_peq.wysylke_zakonczono = None

    wait_for_object.return_value = mock_peq

    with pytest.raises(NotImplementedError):
        task_sprobuj_wyslac_do_pbn(5)

    # Lock should still be cleaned up even on error
    mock_cache_delete.assert_called_once()


def test_task_sprobuj_wyslac_do_pbn_lock_already_acquired(mocker):
    """Test that task skips processing when lock is already acquired"""
    # Mock cache.add to return False (lock already exists)
    mock_cache_add = mocker.patch("pbn_export_queue.tasks.cache.add", return_value=False)
    mock_cache_delete = mocker.patch("pbn_export_queue.tasks.cache.delete")

    wait_for_object = mocker.patch("pbn_export_queue.tasks.wait_for_object")

    result = task_sprobuj_wyslac_do_pbn(5)

    # Should return immediately without processing
    assert result == "ALREADY_PROCESSING"
    wait_for_object.assert_not_called()
    mock_cache_delete.assert_not_called()


def test_task_sprobuj_wyslac_do_pbn_already_completed(mocker):
    """Test that task skips processing when record is already completed"""
    # Mock cache operations
    mock_cache_add = mocker.patch("pbn_export_queue.tasks.cache.add", return_value=True)
    mock_cache_delete = mocker.patch("pbn_export_queue.tasks.cache.delete")

    wait_for_object = mocker.patch("pbn_export_queue.tasks.wait_for_object")

    mock_peq = MagicMock()
    mock_peq.wysylke_zakonczono = "2024-01-01"  # Already completed

    wait_for_object.return_value = mock_peq

    result = task_sprobuj_wyslac_do_pbn(5)

    # Should return without calling send_to_pbn
    assert result == "ALREADY_COMPLETED"
    mock_peq.send_to_pbn.assert_not_called()
    mock_cache_delete.assert_called_once()


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


@pytest.mark.django_db
def test_check_and_send_next_in_queue_with_locks(mocker):
    """Test that check_and_send_next_in_queue respects locks"""
    from pbn_export_queue.tasks import check_and_send_next_in_queue

    # Create test queue items
    items = []
    for i in range(3):
        items.append(
            baker.make(
                PBN_Export_Queue,
                wysylke_podjeto=None,
                wysylke_zakonczono=None,
            )
        )

    # Mock cache.get to return True for first item (locked), False for others
    def mock_cache_get(key):
        if f"{items[0].pk}" in key:
            return "locked"
        return None

    mock_cache = mocker.patch("pbn_export_queue.tasks.cache.get", side_effect=mock_cache_get)
    mock_task_delay = mocker.patch("pbn_export_queue.tasks.task_sprobuj_wyslac_do_pbn.delay")

    result = check_and_send_next_in_queue()

    # Should send only 2 items (not the locked one)
    assert result == 2
    assert mock_task_delay.call_count == 2
    # Check that tasks were called for items 2 and 3, not item 1
    called_pks = [call[0][0] for call in mock_task_delay.call_args_list]
    assert items[0].pk not in called_pks
    assert items[1].pk in called_pks
    assert items[2].pk in called_pks


@pytest.mark.django_db
def test_report_technical_errors_to_rollbar_with_errors(mocker, admin_user):
    """Test that technical errors are reported to Rollbar when they exist."""
    # Create some technical errors (finished with errors)
    for _ in range(3):
        baker.make(
            PBN_Export_Queue,
            rodzaj_bledu=RodzajBledu.TECHNICZNY,
            wysylke_zakonczono=timezone.now(),  # Must be finished
            zamowil=admin_user,
        )

    # Create some MERYTORYCZNY errors (should not be counted)
    baker.make(
        PBN_Export_Queue,
        rodzaj_bledu=RodzajBledu.MERYTORYCZNY,
        wysylke_zakonczono=timezone.now(),
        zamowil=admin_user,
    )

    # Create an unfinished TECHNICZNY error (should not be counted)
    baker.make(
        PBN_Export_Queue,
        rodzaj_bledu=RodzajBledu.TECHNICZNY,
        wysylke_zakonczono=None,
        zamowil=admin_user,
    )

    mock_rollbar = mocker.patch("pbn_export_queue.tasks.rollbar.report_message")

    result = report_technical_errors_to_rollbar()

    assert result == 3
    mock_rollbar.assert_called_once()
    call_args = mock_rollbar.call_args
    assert "3 TECHNICAL errors" in call_args[0][0]
    assert call_args[1]["level"] == "warning"
    assert call_args[1]["extra_data"]["technical_errors_count"] == 3


@pytest.mark.django_db
def test_report_technical_errors_to_rollbar_no_errors(mocker, admin_user):
    """Test that nothing is reported when there are no technical errors."""
    # Create only MERYTORYCZNY errors
    baker.make(
        PBN_Export_Queue,
        rodzaj_bledu=RodzajBledu.MERYTORYCZNY,
        wysylke_zakonczono=timezone.now(),
        zamowil=admin_user,
    )

    mock_rollbar = mocker.patch("pbn_export_queue.tasks.rollbar.report_message")

    result = report_technical_errors_to_rollbar()

    assert result == 0
    mock_rollbar.assert_not_called()
