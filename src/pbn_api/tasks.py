from long_running.util import wait_for_object

from django_bpp.celery_tasks import app


@app.task
def task_sprobuj_wyslac_do_pbn(pk):
    from pbn_api.models import PBN_Export_Queue

    p = wait_for_object(PBN_Export_Queue, pk)
    return p.send_to_pbn()


@app.task
def kolejka_wyczysc_wpisy_bez_rekordow():
    from pbn_api.models import PBN_Export_Queue

    for elem in PBN_Export_Queue.objects.all():
        if not elem.check_if_record_still_exists():
            elem.delete()


@app.task
def kolejka_ponow_wysylke_prac():
    from pbn_api.models import PBN_Export_Queue

    for elem in PBN_Export_Queue.objects.filter(wysylke_zakonczono=None):
        task_sprobuj_wyslac_do_pbn.delay(elem.pk)
