from long_running.util import wait_for_object
from pbn_api.models.queue import SendStatus

from django_bpp.celery_tasks import app


@app.task
def task_sprobuj_wyslac_do_pbn(pk):
    from pbn_api.models import PBN_Export_Queue

    p = wait_for_object(PBN_Export_Queue, pk)
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

        case (
            SendStatus.FINISHED_ERROR
            | SendStatus.FINISHED_OKAY
            | SendStatus.RETRY_AFTER_USER_AUTHORISED
        ):
            return

        case _:
            raise NotImplementedError(
                f"Return status for background send to PBN not supported {res=}"
            )


@app.task
def kolejka_wyczysc_wpisy_bez_rekordow():
    from pbn_api.models import PBN_Export_Queue

    for elem in PBN_Export_Queue.objects.all():
        if not elem.check_if_record_still_exists():
            elem.delete()


@app.task
def kolejka_ponow_wysylke_prac_po_zalogowaniu(pk):
    from pbn_api.models import PBN_Export_Queue

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
