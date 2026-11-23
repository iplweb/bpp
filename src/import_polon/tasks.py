"""Zadania cykliczne importu POLON / absencji."""

from datetime import timedelta

from celery.utils.log import get_task_logger
from django.db.models import Q
from django.utils import timezone

from django_bpp.celery_tasks import app

logger = get_task_logger(__name__)

#: Niezakończony import z plikiem z hasłem kasujemy dopiero po dobie: tyle
#: nie czeka w kolejce i nie trwa żaden żywy przebieg (eksport z POL-on
#: przetwarza się w minuty), więc to na pewno sierota po zabitym workerze.
#: Doba liczy się od utworzenia ORAZ od rozpoczęcia — import, który czekał
#: w kolejce dłużej (np. worker leżał) i właśnie został podjęty, ma świeże
#: ``started_on`` i nie może stracić pliku spod rąk workera.
MAKS_WIEK_NIEZAKONCZONEGO_GODZIN = 24


def usun_zalegle_pliki_z_haslem(maks_wiek_godzin=None):
    """Siatka bezpieczeństwa dla odszyfrowanych plików z hasłem.

    Normalnie plik kasuje sam przebieg importu (``_uruchom_import``). Ten
    nie rusza jednak wcale, gdy import anulowano przed startem (runner liveops
    kończy wtedy operację bez wołania ``run()``), nie kończy się, gdy worker
    zginął twardo (OOM, SIGKILL), a kasowanie mogło się nie udać (błąd
    storage — nazwa zostaje w rekordzie właśnie po to, żeby ponowić). Kasujemy:

    * pliki importów w stanie KOŃCOWYM (``finished_on`` ustawione: sukces,
      błąd, anulowanie) — od razu,
    * pozostałe — gdy od utworzenia minęło więcej niż ``maks_wiek_godzin``
      i import jeszcze się nie rozpoczął lub od rozpoczęcia też minął ten czas.

    Gdyby po tym import jednak ruszył, ``run()`` bez pliku kończy się
    czytelnym komunikatem (``p.error``), nie wyjątkiem. Błąd przy jednym
    rekordzie jest logowany i nie przerywa pozostałych.

    Zwraca liczbę importów, z których usunięto plik.
    """
    from import_polon.models import ImportPlikuAbsencji, ImportPlikuPolon
    from import_polon.utils import usun_stare_katalogi_tymczasowe

    if maks_wiek_godzin is None:
        maks_wiek_godzin = MAKS_WIEK_NIEZAKONCZONEGO_GODZIN
    prog = timezone.now() - timedelta(hours=maks_wiek_godzin)

    usunieto = 0
    for model in (ImportPlikuPolon, ImportPlikuAbsencji):
        qs = (
            model.objects.filter(plik_byl_zaszyfrowany=True)
            .exclude(plik="")
            .filter(
                Q(finished_on__isnull=False)
                | (
                    Q(created_on__lt=prog)
                    & (Q(started_on__isnull=True) | Q(started_on__lt=prog))
                )
            )
            .only("pk", "plik", "plik_byl_zaszyfrowany")
        )
        for imp in qs.iterator():
            try:
                imp.usun_plik_jesli_byl_zaszyfrowany()
            except Exception:
                # Pętla porządkowa ma iść dalej — logujemy z tracebackiem.
                logger.exception(
                    "import_polon: nie udało się sprzątnąć pliku z hasłem (%s pk=%s)",
                    model.__name__,
                    imp.pk,
                )
                continue
            if not imp.plik:
                usunieto += 1

    if usunieto:
        logger.info("import_polon: usunięto %d zaległych plików z hasłem", usunieto)

    # Na hostach, gdzie worker dzieli /tmp z aplikacją — przy okazji katalogi
    # tymczasowe walidacji osierocone przez zabity proces (w kontenerach
    # sprząta je sam formularz przy kolejnym imporcie).
    usun_stare_katalogi_tymczasowe()
    return usunieto


@app.task(ignore_result=True)
def usun_zalegle_pliki_z_haslem_importu_polon():
    """Wrapper Celery — wołany z CELERYBEAT_SCHEDULE."""
    return usun_zalegle_pliki_z_haslem()
