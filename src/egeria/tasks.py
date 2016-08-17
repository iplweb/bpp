# -*- encoding: utf-8 -*-

from celery.utils.log import get_task_logger
from django.core.management import call_command

from django_bpp.util import wait_for_object
from egeria.models.core import EgeriaImport

logger = get_task_logger(__name__)

from django_bpp.celery_tasks import app


@app.task
def analyze_egeriaimport(pk):
    obj = wait_for_object(EgeriaImport, pk)
    obj.analyze()
    obj.diff_tytuly()
    obj.analysis_level += 1
    obj.save()
    msg = u'Ukończono analizę importu osób "%s", <a href="%s">kliknij tutaj, aby otworzyć</a>. '
    call_command('send_message', obj.created_by.username, msg % (obj.get_title(), obj.get_absolute_url()))
