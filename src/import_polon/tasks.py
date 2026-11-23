"""Zadania cykliczne importu POLON / absencji."""

from datetime import timedelta

from celery.utils.log import get_task_logger
from django.db.models import Q
from django.utils import timezone

from django_bpp.celery_tasks import app

logger = get_task_logger(__name__)

#: Po tylu minutach plik z hasłem kasujemy niezależnie od stanu importu.
#: Eksporty z POL-on przetwarzają się w sekundy-minuty, a rdzeń importu
#: wczytuje cały plik do pamięci na samym początku przebiegu.
MAKS_WIEK_PLIKU_Z_HASLEM_MINUT = 60


def usun_zalegle_pliki_z_haslem(maks_wiek_minut=None):
    """Siatka bezpieczeństwa dla odszyfrowanych plików z hasłem.

    Normalnie plik kasuje sam przebieg importu (``_uruchom_import``). Ten
    nie rusza jednak wcale, gdy import anulowano przed startem (runner liveops
    kończy wtedy operację bez wołania ``run()``), a nie kończy się, gdy worker
    zginął twardo (OOM, SIGKILL). Kasujemy więc plik każdego importu z hasłem,
    który jest już zakończony (sukces, błąd, anulowanie) albo starszy niż
    ``maks_wiek_minut`` — bez względu na stan.

    Zwraca liczbę importów, z których usunięto plik.
    """
    from import_polon.models import ImportPlikuAbsencji, ImportPlikuPolon

    if maks_wiek_minut is None:
        maks_wiek_minut = MAKS_WIEK_PLIKU_Z_HASLEM_MINUT
    prog = timezone.now() - timedelta(minutes=maks_wiek_minut)

    usunieto = 0
    for model in (ImportPlikuPolon, ImportPlikuAbsencji):
        qs = (
            model.objects.filter(plik_byl_zaszyfrowany=True)
            .exclude(plik="")
            .filter(Q(finished_on__isnull=False) | Q(created_on__lt=prog))
        )
        for imp in qs:
            imp.usun_plik_jesli_byl_zaszyfrowany()
            usunieto += 1

    if usunieto:
        logger.info("import_polon: usunięto %d zaległych plików z hasłem", usunieto)
    return usunieto


@app.task(ignore_result=True)
def usun_zalegle_pliki_z_haslem_importu_polon():
    """Wrapper Celery — wołany z CELERYBEAT_SCHEDULE."""
    return usun_zalegle_pliki_z_haslem()
