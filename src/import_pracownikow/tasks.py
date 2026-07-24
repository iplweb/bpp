"""Zadania cykliczne modułu importu pracowników."""

from datetime import timedelta

from celery.utils.log import get_task_logger
from django.conf import settings
from django.utils import timezone

from django_bpp.celery_tasks import app

logger = get_task_logger(__name__)


def usun_stare_pliki_importu(dni=None):
    """Kasuje blob `plik_xls` importów starszych niż `dni` dni.

    Rekord ImportPracownikow i jego wiersze ZOSTAJĄ — znika tylko plik
    źródłowy XLS, czyli jedyna część, która realnie zajmuje miejsce na
    wolumenie media. Historia dopasowań pozostaje dostępna w adminie.

    Zwraca liczbę skasowanych blobów.
    """
    from import_pracownikow.models import ImportPracownikow

    if dni is None:
        dni = getattr(settings, "IMPORT_PRACOWNIKOW_RETENCJA_DNI", 90)

    prog = timezone.now() - timedelta(days=dni)
    qs = ImportPracownikow.objects.filter(created_on__lt=prog).exclude(plik_xls="")

    skasowano = 0
    for imp in qs:
        imp.plik_xls.delete(save=False)
        imp.plik_xls = ""
        imp.save(update_fields=["plik_xls"])
        skasowano += 1

    logger.info(
        "import_pracownikow: skasowano %d plików XLS starszych niż %d dni (próg=%s)",
        skasowano,
        dni,
        prog.date(),
    )
    return skasowano


@app.task(ignore_result=True)
def usun_stare_pliki_importu_pracownikow():
    """Wrapper Celery dla retencji plików XLS importu pracowników.

    Wołany z CELERYBEAT_SCHEDULE. Do tej pory istniała wyłącznie komenda
    zarządzająca o tej samej nazwie, ale nikt jej nie wywoływał (ani beat, ani
    Ofelia) — bloby XLS nie były kasowane nigdy.
    """
    return usun_stare_pliki_importu()
