from django.apps import apps
from django.core.cache import cache

from django_bpp.celery_tasks import app
from long_running.util import wait_for_object

from .models import PBN_Export_Queue, SendStatus

# Konfiguracja locków
LOCK_TIMEOUT = 300  # 5 minut timeout dla locka
LOCK_PREFIX = "pbn_export_lock:"


@app.task
def task_sprobuj_wyslac_do_pbn(pk):
    # Spróbuj uzyskać lock dla tego rekordu
    lock_key = f"{LOCK_PREFIX}{pk}"

    # cache.add zwraca True jeśli klucz został dodany (lock uzyskany)
    # False jeśli klucz już istnieje (ktoś już przetwarza ten rekord)
    acquired = cache.add(lock_key, "locked", LOCK_TIMEOUT)

    if not acquired:
        # Ktoś już przetwarza ten rekord - pomiń
        return "ALREADY_PROCESSING"

    try:
        p = wait_for_object(PBN_Export_Queue, pk)

        # Dodatkowe sprawdzenie - może rekord został już wysłany
        # podczas oczekiwania na lock
        p.refresh_from_db()
        if p.wysylke_zakonczono is not None:
            return "ALREADY_COMPLETED"

        res = p.send_to_pbn()

        match res:
            case SendStatus.RETRY_LATER:
                task_sprobuj_wyslac_do_pbn.apply_async(args=[pk], countdown=5 * 60)

            case SendStatus.RETRY_SOON:
                # np. 423 Locked
                task_sprobuj_wyslac_do_pbn.apply_async(args=[pk], countdown=60)

            case SendStatus.RETRY_MUCH_LATER:
                # PraceSerwisoweException
                task_sprobuj_wyslac_do_pbn.apply_async(args=[pk], countdown=60 * 60 * 3)

            case SendStatus.FINISHED_OKAY:
                # After successful send, check for more items in queue
                check_and_send_next_in_queue()
                return

            case SendStatus.FINISHED_ERROR | SendStatus.RETRY_AFTER_USER_AUTHORISED:
                return

            case _:
                raise NotImplementedError(
                    f"Return status for background send to PBN not supported {res=}"
                )

    finally:
        # Zawsze zwolnij lock po zakończeniu przetwarzania
        cache.delete(lock_key)


def check_and_send_next_in_queue():
    """Check if there are more items waiting to be sent and start sending them."""
    # Find the next items that haven't been processed yet
    # Priority order:
    # 1. Items that were never attempted (wysylke_podjeto=None)
    # 2. Items that are waiting but not finished
    next_items = PBN_Export_Queue.objects.filter(
        wysylke_podjeto=None,
        wysylke_zakonczono=None,
    ).order_by("zamowiono")[:5]  # Process up to 5 items at once

    sent_count = 0
    for item in next_items:
        # Sprawdź czy nie ma już locka dla tego elementu
        lock_key = f"{LOCK_PREFIX}{item.pk}"
        if not cache.get(lock_key):
            # Brak locka - można wysyłać
            task_sprobuj_wyslac_do_pbn.delay(item.pk)
            sent_count += 1

    return sent_count


@app.task
def kolejka_wyczysc_wpisy_bez_rekordow():
    for elem in PBN_Export_Queue.objects.all():
        if not elem.check_if_record_still_exists():
            elem.delete()


@app.task
def kolejka_ponow_wysylke_prac_po_zalogowaniu(pk):
    # Użytkownik o ID pk zalogował się.
    # Odśwież do wysyłki prace które były jego po zalogowaniu
    for elem in PBN_Export_Queue.objects.filter(
        retry_after_user_authorised=True, zamowil_id=pk, wysylke_zakonczono=None
    ):
        task_sprobuj_wyslac_do_pbn.delay(elem.pk)

    # ... ale i odświez prace wszystkich użytkowników, którzy mają jego konto
    # jako konto do wysyłki:
    for elem in PBN_Export_Queue.objects.filter(
        retry_after_user_authorised=True,
        zamowil__przedstawiaj_w_pbn_jako_id=pk,
        wysylke_zakonczono=None,
    ):
        task_sprobuj_wyslac_do_pbn.delay(elem.pk)


@app.task
def queue_pbn_export_batch(app_label, model_name, record_ids, user_id):
    """
    Queue multiple records for PBN export in batch.

    Args:
        app_label: Django app label (e.g. 'bpp')
        model_name: Model name (e.g. 'wydawnictwo_ciagle')
        record_ids: List of record IDs to queue
        user_id: User ID who initiated the export
    """
    from django.contrib.auth import get_user_model

    from pbn_api.exceptions import AlreadyEnqueuedError

    User = get_user_model()

    try:
        user = User.objects.get(pk=user_id)
    except User.DoesNotExist:
        return

    model = apps.get_model(app_label, model_name)

    for record_id in record_ids:
        try:
            record = model.objects.get(pk=record_id)
            try:
                PBN_Export_Queue.objects.sprobuj_utowrzyc_wpis(user, record)
                # Send to PBN in background
                queue_entry = PBN_Export_Queue.objects.filter_rekord_do_wysylki(
                    record
                ).first()
                if queue_entry:
                    task_sprobuj_wyslac_do_pbn.delay(queue_entry.pk)
            except AlreadyEnqueuedError:
                # Record already in queue, skip
                pass
        except model.DoesNotExist:
            # Skip records that don't exist
            pass
        except Exception:
            # Skip records with other errors
            pass
