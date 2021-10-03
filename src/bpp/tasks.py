# -*- encoding: utf-8 -*-
import os

from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured
from django.core.management import call_command

try:
    from django.core.urlresolvers import reverse
except ImportError:
    from django.urls import reverse

from celeryui.interfaces import IWebTask
from celeryui.models import Report

from bpp.models import (
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Uczelnia,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)
from bpp.util import remove_old_objects

logger = get_task_logger(__name__)

from django_bpp.celery_tasks import app


@app.task(ignore_result=True)
def remove_file(path):
    if path.startswith(os.path.join(settings.MEDIA_ROOT, "report")):
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
        msg = 'Ukończono generowanie raportu "%s", <a href="%s">kliknij tutaj, aby otworzyć</a>. '
        url = reverse("bpp:podglad-raportu", args=(report.uid,))
        call_command(
            "send_message",
            report.ordered_by.username,
            msg % (IWebTask(report).title, url),
        )

    return execute()


task_limits = {}


def my_limit(fun):
    res = task_limits.get(fun)
    if not res or (res.successful() or res.failed()):
        task_limits[fun] = fun.apply_async(
            countdown=settings.MAT_VIEW_REFRESH_COUNTDOWN
        )
        return

    if res:
        logger.info("Task %r has been revoked." % res.id)
        res.revoke()
        task_limits[fun] = fun.apply_async(
            countdown=settings.MAT_VIEW_REFRESH_COUNTDOWN
        )


@app.task(ignore_result=True, store_errors_even_if_ignored=True)
def remove_old_report_files():
    return remove_old_objects(Report, field_name="started_on")


def _zaktualizuj_liczbe_cytowan(klasy=None):
    if klasy is None:
        klasy = (
            Wydawnictwo_Ciagle,
            Wydawnictwo_Zwarte,
            Praca_Doktorska,
            Praca_Habilitacyjna,
        )

    for uczelnia in Uczelnia.objects.all():
        try:
            client = uczelnia.wosclient()
        except ImproperlyConfigured:
            continue

        # FIXME: jeżeli jest >1 uczelnia w systemie, to odpytanie
        # obiektów nastąpi w sposób wielokrotny...

        for klass in klasy:
            filtered = (
                klass.objects.all()
                .exclude(doi=None)
                .exclude(pubmed_id=None)
                .values("id", "doi", "pubmed_id")
            )

            for grp in client.query_multiple(filtered):
                for k, item in grp.items():
                    changed = False

                    timesCited = item.get("timesCited")
                    doi = item.get("doi")
                    pubmed_id = item.get("pmid")

                    obj = klass.objects.get(pk=k)

                    if timesCited is not None:
                        if obj.liczba_cytowan != timesCited:
                            obj.liczba_cytowan = timesCited
                            changed = True

                    if pubmed_id is not None:
                        if obj.pubmed_id != pubmed_id:
                            obj.pubmed_id = pubmed_id
                            changed = True

                    if doi is not None:
                        if obj.doi != doi:
                            obj.doi = doi
                            changed = True

                    if changed:
                        obj.save()


@app.task
def zaktualizuj_liczbe_cytowan():
    _zaktualizuj_liczbe_cytowan()
