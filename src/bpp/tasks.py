import os

from celery.utils.log import get_task_logger
from celery_singleton import Singleton
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from bpp.models import (
    Praca_Doktorska,
    Praca_Habilitacyjna,
    Uczelnia,
    Wydawnictwo_Ciagle,
    Wydawnictwo_Zwarte,
)
from django_bpp.celery_tasks import app

logger = get_task_logger(__name__)


@app.task(ignore_result=True)
def remove_file(path):
    if path.startswith(os.path.join(settings.MEDIA_ROOT, "report")):
        logger.warning("Removing %r", path)
        os.unlink(path)


def _zaktualizuj_liczbe_cytowan(klasy=None):  # noqa: C901
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


@app.task(
    base=Singleton,
    # Lock przez 2h — task realnie potrzebuje tyle przy dużym korpusie
    # publikacji × kilkudziesięciu requestach do WoS API. Po 2h
    # uznajemy zombie-task i odblokowujemy, żeby nowe wywołania nie
    # zostały zablokowane przez zawieszony lock w Redisie.
    lock_expiry=2 * 60 * 60,
    # Hard time limit żeby zawieszony WoS request nie blokował workera
    # w nieskończoność.
    time_limit=2 * 60 * 60,
    soft_time_limit=int(1.9 * 60 * 60),
)
def zaktualizuj_liczbe_cytowan():
    """Update WoS citation counts. Singleton — dwa równoczesne uruchomienia
    odpytałyby WoS API zdublowanie. Lock w Redisie zapewnia że tylko jeden
    worker wykonuje task naraz (cluster-wide)."""
    _zaktualizuj_liczbe_cytowan()
