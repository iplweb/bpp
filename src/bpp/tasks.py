from datetime import timedelta
from pathlib import Path

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
    """Usuń plik raportu — wyłącznie z dedykowanego katalogu ``MEDIA_ROOT/report``.

    Hardening: ścieżkę rozwiązujemy przez ``Path.resolve()`` (łamie ``..`` oraz
    dowiązania symboliczne) i wymagamy, by leżała WEWNĄTRZ katalogu raportów.
    Poprzednie ``path.startswith(MEDIA_ROOT/report)`` przepuszczało zarówno
    rodzeństwo o wspólnym prefiksie (``…/report-evil/x``), jak i traversal
    (``…/report/../../etc/passwd``). Brak pliku nie jest błędem — task bywa
    ponawiany, a plik mógł już zostać usunięty (idempotencja).
    """
    report_dir = Path(settings.MEDIA_ROOT, "report").resolve()
    try:
        target = Path(path).resolve()
    except (OSError, ValueError, RuntimeError):
        # np. pętla symlinków (ELOOP) albo NUL w ścieżce
        logger.warning("remove_file: nie można rozwiązać ścieżki %r — pomijam", path)
        return

    if target == report_dir or not target.is_relative_to(report_dir):
        logger.warning(
            "remove_file: ścieżka %r poza katalogiem raportów %s — pomijam",
            path,
            report_dir,
        )
        return

    logger.warning("Removing %r", str(target))
    try:
        target.unlink()
    except FileNotFoundError:
        pass  # Plik już usunięty — idempotencja, nie błąd
    except IsADirectoryError:
        # Nie kasujemy katalogów — remove_file jest kontraktem na pojedyncze pliki
        logger.warning("remove_file: %r to katalog, nie plik — pomijam", str(target))


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


# Domyślna retencja nieudanych prób logowania (django-axes AccessAttempt) w
# dniach. AXES_RESET_ON_SUCCESS kasuje wpisy TYLKO po udanym logowaniu tego
# samego (login, IP) — wpisy generowane przez boty skanujące /admin/login/
# nigdy nie doczekają się „swojego" udanego logowania i zostawałyby w bazie
# bezterminowo. 90 dni: wielokrotnie powyżej AXES_COOLOFF_TIME (30 min), więc
# retencja nigdy nie skasuje wpisu wciąż uczestniczącego w lockoucie, a
# jednocześnie zostawia okno na forensykę kampanii brute-force.
AXES_ACCESSATTEMPT_RETENTION_DAYS = 90


@app.task(ignore_result=True)
def usun_stare_proby_logowania_axes(days=AXES_ACCESSATTEMPT_RETENTION_DAYS):
    """Usuwa wpisy axes AccessAttempt starsze niż `days` dni.

    Dotyczy wyłącznie AccessAttempt (nieudane próby logowania — to ta tabela
    puchnie od skanerów). AccessLog (udane logowania/wylogowania) NIE jest
    ruszany.
    """
    from axes.models import AccessAttempt
    from django.utils import timezone

    cutoff = timezone.now() - timedelta(days=days)
    deleted, _ = AccessAttempt.objects.filter(attempt_time__lt=cutoff).delete()
    logger.info(
        "axes AccessAttempt: usunięto %d wpisów starszych niż %d dni (cutoff=%s)",
        deleted,
        days,
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


# Pola aktualizowane z WoS — te same, które mapuje `_POLA_CYTOWAN`.
_POLA_DO_BULK_UPDATE = [atrybut for _, atrybut in _POLA_CYTOWAN]


def _pobierz_wyniki_wos(klass, clients):
    """Odpytaj WoS o korpus danego typu (rekordy z DOI+PMID); zwróć {id: pola}.

    Korpus pobieramy RAZ na typ i puszczamy przez wszystkie skonfigurowane
    klienty WoS, scalając wyniki (liczba cytowań to metryka globalna, nie
    per-uczelnia). Pusty korpus → pusty słownik (bez odpytywania WoS).
    """
    filtered = list(
        klass.objects.exclude(doi=None)
        .exclude(pubmed_id=None)
        .values("id", "doi", "pubmed_id")
    )
    if not filtered:
        return {}

    wos_items = {}
    for client in clients:
        for grp in client.query_multiple(filtered):
            wos_items.update(grp)
    return wos_items


def _zaktualizuj_klase_z_wos(klass, clients):
    """Zaktualizuj (hurtowo) pola WoS dla jednego typu publikacji.

    Rekordy doczytujemy jednym ``in_bulk`` zamiast ``get()`` per wynik, a
    zapis idzie jednym ``bulk_update`` zamiast ``save()`` per rekord.
    """
    wos_items = _pobierz_wyniki_wos(klass, clients)
    if not wos_items:
        return

    rekordy = klass.objects.in_bulk(list(wos_items.keys()))
    do_zapisu = []
    for pk, item in wos_items.items():
        obj = rekordy.get(pk)
        if obj is not None and _zaktualizuj_pola_z_wos(obj, item):
            do_zapisu.append(obj)

    if do_zapisu:
        klass.objects.bulk_update(do_zapisu, _POLA_DO_BULK_UPDATE, batch_size=500)


def _zaktualizuj_liczbe_cytowan(klasy=None):
    """Zaktualizuj liczbę cytowań (i pola WoS) hurtowo, jednym przebiegiem korpusu.

    Wcześniej: N uczelni × cały korpus × ``get()``+``save()`` na każdy wynik.
    Teraz: korpus raz na typ, wyniki wszystkich klientów WoS scalone,
    ``in_bulk`` + ``bulk_update``. ``bulk_update`` omija sygnały ``save()``
    (jak inne masowe update'y w tym kodzie) — dla pól cytowań to akceptowalne;
    odświeżenie mat-view/cache i tak następuje osobnym przebiegiem.
    """
    if klasy is None:
        klasy = (
            Wydawnictwo_Ciagle,
            Wydawnictwo_Zwarte,
            Praca_Doktorska,
            Praca_Habilitacyjna,
        )

    clients = []
    for uczelnia in Uczelnia.objects.all():
        try:
            clients.append(uczelnia.wosclient())
        except ImproperlyConfigured:
            continue

    if not clients:
        return

    for klass in klasy:
        _zaktualizuj_klase_z_wos(klass, clients)


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
