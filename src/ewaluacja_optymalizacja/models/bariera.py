"""Bariera bazodanowa (advisory lock) dla singletonów statusu zadań Celery.

Druga — NIEZALEŻNA OD REDISA — warstwa ochrony przed równoległymi
przebiegami dwóch najgroźniejszych zadań optymalizacji
(``optimize_and_unpin_task`` i ``unpin_all_sensible_task``). Lock w Redisie
(``celery_singleton.Singleton``) sam nie wystarcza, bo ``unlock_all`` /
``clear_locks`` na sygnale ``worker_ready`` (``django_bpp/celery_tasks.py``)
kasuje WSZYSTKIE locki globalnie: przy wielu kontenerach workera rolling
restart któregokolwiek z nich zwalnia w środku 2–3-godzinnego przebiegu lock
chroniący zadanie trwające na INNYM workerze. Bez tej bariery drugie
uruchomienie weszłoby w masowe odpinanie przypięć całej uczelni i zdublowało
efekty pierwszego.

Wzorzec skopiowany z ``deduplikator_autorow.tasks._przejmij_slot_skanu``
(#629). Kluczowe: wzajemne wykluczanie stoi na ``pg_advisory_xact_lock``, NIE
na ``select_for_update``. ``SELECT ... FOR UPDATE`` blokuje ZNALEZIONE
wiersze — gdy żaden przebieg nie trwa, zbiór wynikowy singletona pk=1 może być
pusty (albo z ``w_trakcie=False``) i wszystkie równoległe transakcje
przechodzą dalej (phantom read). Advisory lock zakładany jest na UMOWNYM
obiekcie istniejącym niezależnie od wierszy, więc działa też przy pustej
tabeli. Wariant ``_xact_`` zwalnia się sam na COMMIT/ROLLBACK i przy zerwaniu
połączenia — nie wprowadza nowej klasy zombie.
"""

from datetime import timedelta

from django.db import connection, transaction
from django.utils import timezone


def zajmij_slot_pod_bariera(model_cls, lock_id, task_id, stale_after, logger=None):
    """Atomowo zajmij „slot" przebiegu singletona ``model_cls`` (pk=1).

    Zwraca ``True``, gdy wołający może działać (slot był wolny, przeterminowany
    albo należał już do tego samego ``task_id``), a ``False``, gdy trwa inny,
    ŚWIEŻY przebieg (wołający ma się wycofać).

    Wpisy ``w_trakcie=True`` starsze niż ``stale_after`` sekund traktowane są
    jako zombie po ubitym workerze i zostają przejęte — inaczej jeden SIGKILL
    zakleszczyłby zadanie na zawsze.

    Zapis stanu robiony jest przez ``filter(pk=1).update(...)`` (a nie
    ``self.save()``), spójnie z kierunkiem PR #646.
    """
    stale_cutoff = timezone.now() - timedelta(seconds=stale_after)

    with transaction.atomic():
        # MUSI być pierwszą instrukcją w transakcji — cała sekcja krytyczna
        # (odczyt stanu + decyzja + zapis) ma iść pod tym lockiem.
        with connection.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(%s)", [lock_id])

        obj = model_cls.objects.filter(pk=1).first()

        trwa_obcy_swiezy = (
            obj is not None
            and obj.w_trakcie
            and obj.task_id != task_id
            and obj.data_rozpoczecia is not None
            and obj.data_rozpoczecia > stale_cutoff
        )
        if trwa_obcy_swiezy:
            if logger is not None:
                logger.warning(
                    "%s: przebieg już trwa (task_id=%s, start=%s) — "
                    "wycofuję się (bariera bazodanowa).",
                    model_cls.__name__,
                    obj.task_id,
                    obj.data_rozpoczecia,
                )
            return False

        if (
            obj is not None
            and obj.w_trakcie
            and obj.task_id != task_id
            and logger is not None
        ):
            logger.warning(
                "%s: przeterminowuję osierocony przebieg (task_id=%s, start=%s) "
                "starszy niż %ss i przejmuję slot.",
                model_cls.__name__,
                obj.task_id,
                obj.data_rozpoczecia,
                stale_after,
            )

        zaktualizowane = model_cls.objects.filter(pk=1).update(
            w_trakcie=True,
            task_id=task_id,
            data_rozpoczecia=timezone.now(),
        )
        if not zaktualizowane:
            model_cls.objects.create(
                pk=1,
                w_trakcie=True,
                task_id=task_id,
                data_rozpoczecia=timezone.now(),
            )
        return True


def zwolnij_slot(model_cls, task_id):
    """Zwolnij slot singletona ``model_cls`` — ale TYLKO gdy wciąż nasz.

    Warunek ``task_id=task_id`` chroni przed skasowaniem stanu przejętego już
    przez nowszy przebieg (który przeterminował nasz wpis jako zombie).
    """
    model_cls.objects.filter(pk=1, task_id=task_id).update(
        w_trakcie=False,
        data_zakonczenia=timezone.now(),
    )
