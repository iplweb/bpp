import os

from celery.utils.log import get_task_logger
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

try:
    pass
except ImportError:
    pass

from bpp.models import (
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Uczelnia,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)

logger = get_task_logger(__name__)

from django_bpp.celery_tasks import app


@app.task(ignore_result=True)
def remove_file(path):
    if path.startswith(os.path.join(settings.MEDIA_ROOT, "report")):
        logger.warning("Removing %r" % path)
        os.unlink(path)


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
