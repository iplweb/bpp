# -*- encoding: utf-8 -*-
import os

from django.core.management import call_command
from django.core.urlresolvers import reverse
from celeryui.interfaces import IWebTask
from django.conf import settings
from celery.utils.log import get_task_logger

logger = get_task_logger(__name__)

from django_bpp.celery import app




@app.task
def remove_file(path):
    if path.startswith(os.path.join(settings.MEDIA_ROOT, 'report')):
        logger.warning("Removing %r" % path)
        os.unlink(path)


@app.task
def make_report(uid):
    from celeryui.models import Report
    from bpp import reports  # for registry

    reports  # pycharm, don't clean this plz

    report = Report.objects.get(uid=uid)
    report.started()

    def execute():
        report.execute(raise_exceptions=True)
        msg = u'Ukończono generowanie raportu "%s", <a href="%s">kliknij tutaj, aby otworzyć</a>. '
        url = reverse("bpp:podglad-raportu", args=(report.uid, ))
        call_command('send_message', report.ordered_by.username, msg % (IWebTask(report).title, url))

    return execute()

task_limits = {}


def my_limit(fun):
    res = task_limits.get(fun)
    if not res or (res.successful() or res.failed()):
        task_limits[fun] = fun.apply_async(countdown=settings.MAT_VIEW_REFRESH_COUNTDOWN)
        return

    if res:
        logger.info("Task %r has been revoked." % res.id)
        res.revoke()
        task_limits[fun] = fun.apply_async(countdown=settings.MAT_VIEW_REFRESH_COUNTDOWN)


@app.task
def zaktualizuj_opis(klasa, pk):
    try:
        obj = klasa.objects.get(pk=pk)
    except Exception:
        logger.exception('Problem z pobraniem obiektu')

    obj.zaktualizuj_cache(tylko_opis=True)

@app.task
def zaktualizuj_zrodlo(pk):
    from bpp.models import Zrodlo, Rekord

    z = Zrodlo.objects.get(pk=pk)
    for rekord in Rekord.objects.filter(zrodlo=z):
        rekord.original.zaktualizuj_cache(tylko_opis=True)
