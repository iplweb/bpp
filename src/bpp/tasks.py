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


# Mapowanie kluczy z odpowiedzi WoS API na atrybuty modelu publikacji.
# Każdy wpis: (klucz_w_odpowiedzi, atrybut_modelu).
_POLA_CYTOWAN = (
    ("timesCited", "liczba_cytowan"),
    ("pmid", "pubmed_id"),
    ("doi", "doi"),
)


def _zaktualizuj_pola_z_wos(obj, item):
    """Nadpisz pola `obj` wartościami z `item` (odpowiedź WoS).

    Pole jest aktualizowane tylko gdy nowa wartość nie jest None ORAZ różni
    się od bieżącej. Zwraca True, jeśli cokolwiek się zmieniło.
    """
    changed = False
    for klucz, atrybut in _POLA_CYTOWAN:
        wartosc = item.get(klucz)
        if wartosc is not None and getattr(obj, atrybut) != wartosc:
            setattr(obj, atrybut, wartosc)
            changed = True
    return changed


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
                    obj = klass.objects.get(pk=k)
                    if _zaktualizuj_pola_z_wos(obj, item):
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
