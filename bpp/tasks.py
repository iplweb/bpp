# -*- encoding: utf-8 -*-
import os

from django.db import connection
from django.core.urlresolvers import reverse
from django.db import transaction
from django_transaction_signals import defer
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

    @transaction.commit_on_success
    def execute():
        from monitio import api

        report.execute(raise_exceptions=True)
        msg = u'Ukończono generowanie raportu "%s", <a href="%s">kliknij tutaj, aby otworzyć</a>. '
        url = reverse("bpp:podglad-raportu", args=(report.uid, ))
        defer(api.create_message,
              level=api.constants.SUCCESS,
              to_user=report.ordered_by,
              message=msg % (IWebTask(report).title, url),
              subject="Informacja", sse=True, url=url)

    return execute()


@app.task
def refresh_autorzy_mat_view():
    """UWAGA: to zadanie winno być uruchamiane przez jednego workera,
    nie więcej niż jedno na cały system jednocześnie."""
    logger.info("refresh mat view autorzy started...")
    from bpp.models.cache import Autorzy
    Autorzy.objects.refresh_materialized_view()
    logger.info("refresh mat view autorzy done!")


@app.task
def refresh_rekord_mat_view():
    """UWAGA: to zadanie winno być uruchamiane przez jednego workera,
    nie więcej niż jedno na cały system jednocześnie."""
    logger.info("refresh mat view rekord started...")
    from bpp.models.cache import Rekord
    Rekord.objects.refresh_materialized_view()
    logger.info("refresh mat view rekord done!")


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
def refresh_rekord():
    my_limit(refresh_rekord_mat_view)


@app.task
def refresh_autorzy():
    my_limit(refresh_autorzy_mat_view)


@app.task
def zaktualizuj_opis(klasa, pk):

    # XXX TODO czy to jest potrzebne tutja?
    #import django
    #django.setup()
    # XXX ENDTODO

    try:
        obj = klasa.objects.get(pk=pk)
    except Exception:
        logger.exception('Problem z pobraniem obiektu')

    obj.zaktualizuj_cache(tylko_opis=True)

    refresh_rekord.delay()
    refresh_autorzy.delay()

@app.task
def zaktualizuj_zrodlo(pk):
    from bpp.models import Zrodlo, Rekord

    z = Zrodlo.objects.get(pk=pk)
    for rekord in Rekord.objects.filter(zrodlo=z):
        rekord.original.zaktualizuj_cache(tylko_opis=True)

    refresh_rekord.delay()