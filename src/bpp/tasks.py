import os

from celery import shared_task
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


# Domyślna retencja logów LOGOWANIA (django-easy-audit LoginEvent) w
# miesiącach. Logi logowania zawierają dane osobowe (login, IP, czas) — RODO
# wymaga minimalizacji (art. 5), więc nie trzymamy ich bezterminowo. 24 mies.
# pokrywa benchmark PCI-DSS (>= 1 rok) z zapasem na forensykę incydentów.
# UWAGA: logi EDYCJI (CRUDEvent) to inna kategoria — tu NIE są ruszane
# (zostają bezterminowo, decyzja merytoryczna).
EASYAUDIT_LOGINEVENT_RETENTION_MONTHS = 24


@app.task(ignore_result=True)
def usun_stare_logi_logowania_easyaudit(
    months=EASYAUDIT_LOGINEVENT_RETENTION_MONTHS,
):
    """Usuwa wpisy LoginEvent starsze niż `months` miesięcy (retencja RODO).

    Usuwa wyłącznie LoginEvent (kto/kiedy/skąd się logował) — NIE dotyka
    CRUDEvent (historia zmian rekordów), który zostaje bezterminowo.
    """
    from dateutil.relativedelta import relativedelta
    from django.utils import timezone
    from easyaudit.models import LoginEvent

    cutoff = timezone.now() - relativedelta(months=months)
    deleted, _ = LoginEvent.objects.filter(datetime__lt=cutoff).delete()
    logger.info(
        "easyaudit LoginEvent: usunięto %d wpisów starszych niż %d mies. (cutoff=%s)",
        deleted,
        months,
        cutoff.date(),
    )
    return deleted


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


#: Maksymalna liczba eksportowanych rekordów. Zabezpiecza przed OOM przy
#: autorach z gigantyczną liczbą prac (eksport materializuje instancje
#: konkretnych modeli, więc jest N+1 — twardy limit jest tańszy niż ryzyko).
#: Wartość musi być spójna z synchronicznym widokiem
#: ``bpp.views.eksport_autora.MAKS_EKSPORT``.
MAKS_EKSPORT_AUTORA = 5000


def _zbuduj_tresc_eksportu_autora(autor, format: str) -> str:
    """Zbuduj treść eksportu IDENTYCZNIE jak widok synchroniczny.

    Ten sam slice (``[:MAKS_EKSPORT]``), ten sam formater i ta sama notka
    o obcięciu w BibTeX-ie — parytet bajt-w-bajt z dotychczasowym eksportem.
    """
    from bpp.export.bibtex import export_to_bibtex
    from bpp.export.ris import export_to_ris
    from bpp.models import Rekord

    qs = Rekord.objects.prace_autora(autor)
    wszystkich = qs.count()
    oryginaly = [r.original for r in qs[:MAKS_EKSPORT_AUTORA]]

    if format == "ris":
        # RIS jest formatem czysto liniowym — brak miejsca na komentarz o
        # obcięciu, polegamy wyłącznie na samym limicie (jak widok sync).
        return export_to_ris(oryginaly)

    tekst = export_to_bibtex(oryginaly)
    if wszystkich > MAKS_EKSPORT_AUTORA:
        tekst = (
            f"% Wyeksportowano pierwsze {len(oryginaly)} z {wszystkich} prac "
            f"(limit {MAKS_EKSPORT_AUTORA}).\n\n" + tekst
        )
    return tekst


@shared_task(bind=True)
def generuj_eksport_autora(self, task_id: str):
    """Zbuduj plik eksportu BibTeX/RIS dla autora i zapisz go w zadaniu.

    Args:
        task_id: UUID rekordu ``AutorEksportTask`` (jako str).
    """
    from django.core.files.base import ContentFile
    from django.utils import timezone

    from bpp.models import AutorEksportTask

    task = AutorEksportTask.objects.get(pk=task_id)
    task.status = "running"
    task.started_at = timezone.now()
    task.celery_task_id = self.request.id or ""
    task.save()

    try:
        tekst = _zbuduj_tresc_eksportu_autora(task.autor, task.format)
        task.result_file.save(task.nazwa_pliku, ContentFile(tekst.encode("utf-8")))
        task.status = "completed"
        task.completed_at = timezone.now()
        task.save()
        return {"status": "success", "task_id": str(task_id)}
    except Exception as e:
        task.status = "failed"
        task.error_message = str(e)
        task.completed_at = timezone.now()
        task.save()
        raise


@shared_task
def usun_stare_eksporty_autora():
    """Usuń rekordy AutorEksportTask i ich pliki starsze niż 7 dni."""
    from bpp.models import AutorEksportTask
    from bpp.util import remove_old_objects

    return remove_old_objects(
        AutorEksportTask,
        file_field="result_file",
        field_name="created_at",
        days=7,
    )
