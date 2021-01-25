from django_bpp.celery_tasks import app
from django_bpp.util import wait_for_object
from raport_slotow.models.uczelnia import RaportSlotowUczelnia


@app.task
def wygeneruj_raport_slotow_uczelnia(pk):
    rsu = wait_for_object(RaportSlotowUczelnia, pk)
    rsu.task_create_report()
