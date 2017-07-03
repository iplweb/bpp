# -*- encoding: utf-8 -*-
import time
from celery.utils.log import get_task_logger
from django.core.management import call_command
from django.core.urlresolvers import reverse

from django_bpp.util import wait_for_object
from egeria.models.core import EgeriaImport
from notifications import send_redirect

logger = get_task_logger(__name__)

from django_bpp.celery_tasks import app


@app.task
def analyze_egeriaimport(pk):
    obj = wait_for_object(EgeriaImport, pk)
    obj.analyze()
    # TODO: wyrzuć diff_tytuły,
    # TODO: przekieruj na stronę "reset import state"
    obj.diff_tytuly()
    obj.analysis_level += 1
    obj.save()
    msg = 'Ukończono analizę importu osób "%s", <a href="%s">kliknij tutaj, aby otworzyć</a>. '
    call_command('send_message', obj.created_by.username, msg % (obj.get_title(), obj.get_absolute_url()))


@app.task
def next_import_step(pk, username, url, messageId):
    """
    Przejdź do kolejnego kroku importu. Potencjalnie, uruchom funkcję EgeriaImport.next_import_step,
    ale jest to opcja (w sytuacji, gdy chcemy przejść do kolejnego podglądu kroku importu).

    :param pk: ID obiektu EgeriaImport, którego dotyczy to zadanie
    :param callback: funkcja do uruchomienia po wykonaniu zadania
    :return:
    """
    obj = wait_for_object(EgeriaImport, pk)
    obj.next_import_step()
    send_redirect(username, url, messageId)

@app.task
def reset_import_state(pk, username, messageId):
    obj = wait_for_object(EgeriaImport, pk)

    while obj.analyzed is False:
        time.sleep(1)
        obj.refresh_from_db()

    obj.reset_import_steps()
    obj.next_import_step()
    send_redirect(username, reverse("egeria:diff_tytul_create", args=(pk,)), messageId)