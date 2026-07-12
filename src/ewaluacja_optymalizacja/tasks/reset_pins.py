"""Taski resetowania przypięć."""

import logging
from datetime import datetime

from celery import shared_task
from celery_singleton import Singleton

from ewaluacja_liczba_n.models import LiczbaNDlaUczelni

from .helpers import _wait_for_denorm
from .optimization import _run_bulk_optimization

logger = logging.getLogger(__name__)


def _reset_pins_for_authors(autorzy_ids, task, snapshot_pk, logger_func):
    """Reset pins for all authors in years 2022-2025."""
    from django.db.models import Q

    from bpp.models import (
        Patent_Autor,
        Wydawnictwo_Ciagle_Autor,
        Wydawnictwo_Zwarte_Autor,
    )

    base_filter = Q(
        rekord__rok__gte=2022, rekord__rok__lte=2025, autor_id__in=autorzy_ids
    )

    updated_count = 0

    # Wydawnictwo Ciągłe Autor
    count_ciagle = Wydawnictwo_Ciagle_Autor.objects.filter(base_filter).update(
        przypieta=True
    )
    updated_count += count_ciagle
    logger_func(
        f"Reset {count_ciagle} pins in Wydawnictwo_Ciagle_Autor for {len(autorzy_ids)} authors"
    )

    task.update_state(
        state="PROGRESS",
        meta={
            "step": "resetting",
            "progress": 50,
            "snapshot_id": snapshot_pk,
            "total_authors": len(autorzy_ids),
            "reset_ciagle": count_ciagle,
        },
    )

    # Wydawnictwo Zwarte Autor
    count_zwarte = Wydawnictwo_Zwarte_Autor.objects.filter(base_filter).update(
        przypieta=True
    )
    updated_count += count_zwarte
    logger_func(
        f"Reset {count_zwarte} pins in Wydawnictwo_Zwarte_Autor for {len(autorzy_ids)} authors"
    )

    task.update_state(
        state="PROGRESS",
        meta={
            "step": "resetting",
            "progress": 70,
            "snapshot_id": snapshot_pk,
            "total_authors": len(autorzy_ids),
            "reset_ciagle": count_ciagle,
            "reset_zwarte": count_zwarte,
        },
    )

    # Patent Autor
    count_patent = Patent_Autor.objects.filter(base_filter).update(przypieta=True)
    updated_count += count_patent
    logger_func(
        f"Reset {count_patent} pins in Patent_Autor for {len(autorzy_ids)} authors"
    )

    task.update_state(
        state="PROGRESS",
        meta={
            "step": "waiting_denorm",
            "progress": 80,
            "snapshot_id": snapshot_pk,
            "total_authors": len(autorzy_ids),
            "reset_ciagle": count_ciagle,
            "reset_zwarte": count_zwarte,
            "reset_patent": count_patent,
            "total_reset": updated_count,
        },
    )

    logger_func(
        f"Reset complete. Total pins reset: {updated_count} "
        f"(Ciągłe: {count_ciagle}, Zwarte: {count_zwarte}, Patent: {count_patent})"
    )

    return count_ciagle, count_zwarte, count_patent, updated_count


@shared_task(
    base=Singleton,
    unique_on=["uczelnia_id", "dyscyplina_id"],
    lock_expiry=3600,
    bind=True,
    time_limit=1800,
)
def reset_discipline_pins_task(
    self, uczelnia_id, dyscyplina_id, owner_id=None, algorithm_mode="two-phase"
):
    """Reset przypięć JEDNEJ dyscypliny (2022-2025) + optymalizacja — w tle.

    Wydzielone z widoku ``reset_discipline_pins``: wcześniej request wisiał
    do 10 minut, śpiąc w pętli i odpytując globalne ``DirtyInstance.count()``
    (czekał też na cudzą denormalizację). Teraz widok tylko zleca to zadanie
    i przekierowuje na stronę statusu; całe czekanie na denorm dzieje się tu,
    w workerze (``_wait_for_denorm`` raportuje postęp przez ``update_state``).
    """
    from datetime import datetime

    from django.contrib.auth import get_user_model
    from django.db import transaction
    from django.db.models import Q

    from bpp.models import (
        Autor_Dyscyplina,
        Dyscyplina_Naukowa,
        Patent_Autor,
        Uczelnia,
        Wydawnictwo_Ciagle_Autor,
        Wydawnictwo_Zwarte_Autor,
    )
    from snapshot_odpiec.models import SnapshotOdpiec

    from .optimization import solve_single_discipline_task

    uczelnia = Uczelnia.objects.get(pk=uczelnia_id)
    dyscyplina = Dyscyplina_Naukowa.objects.get(pk=dyscyplina_id)
    owner = (
        get_user_model().objects.filter(pk=owner_id).first()
        if owner_id is not None
        else None
    )

    self.update_state(state="PROGRESS", meta={"step": "collecting", "progress": 10})

    autorzy_ids = set(
        Autor_Dyscyplina.objects.filter(
            rok__gte=2022, rok__lte=2025, dyscyplina_naukowa=dyscyplina
        )
        .values_list("autor_id", flat=True)
        .distinct()
    )

    self.update_state(
        state="PROGRESS",
        meta={"step": "snapshot", "progress": 20, "total_authors": len(autorzy_ids)},
    )

    with transaction.atomic():
        snapshot = SnapshotOdpiec.objects.create(
            owner=owner,
            comment=f"przed resetem przypięć - {dyscyplina.nazwa}",
        )

    self.update_state(
        state="PROGRESS",
        meta={"step": "resetting", "progress": 30, "snapshot_id": snapshot.pk},
    )

    base_filter = Q(
        rekord__rok__gte=2022,
        rekord__rok__lte=2025,
        dyscyplina_naukowa=dyscyplina,
        autor_id__in=autorzy_ids,
    )
    updated_count = 0
    for model in (Wydawnictwo_Ciagle_Autor, Wydawnictwo_Zwarte_Autor, Patent_Autor):
        updated_count += model.objects.filter(base_filter).update(przypieta=True)
        logger.info(
            f"Reset pins in {model.__name__} for discipline '{dyscyplina.nazwa}'"
        )

    _wait_for_denorm(
        self,
        progress_start=40,
        progress_range=40,
        meta_extra={"snapshot_id": snapshot.pk, "total_reset": updated_count},
        logger_func=logger.info,
    )

    # Optymalizacja tej dyscypliny (jeśli ma zdefiniowaną liczbę N).
    liczba_n_obj = LiczbaNDlaUczelni.objects.filter(
        uczelnia=uczelnia, dyscyplina_naukowa=dyscyplina
    ).first()

    optymalizacja_uruchomiona = False
    if liczba_n_obj is not None:
        self.update_state(
            state="PROGRESS",
            meta={
                "step": "optimization_start",
                "progress": 90,
                "snapshot_id": snapshot.pk,
                "total_reset": updated_count,
            },
        )
        # Jesteśmy już w workerze — uruchamiamy optymalizację synchronicznie
        # (inline), zamiast rozgałęziać kolejne zadanie.
        solve_single_discipline_task(
            uczelnia.pk,
            dyscyplina.pk,
            float(liczba_n_obj.liczba_n),
            algorithm_mode=algorithm_mode,
        )
        optymalizacja_uruchomiona = True
    else:
        logger.warning(
            f"No LiczbaNDlaUczelni for discipline '{dyscyplina.nazwa}', "
            "skipping optimization"
        )

    return {
        "uczelnia_id": uczelnia_id,
        "dyscyplina_id": dyscyplina_id,
        "dyscyplina_nazwa": dyscyplina.nazwa,
        "snapshot_id": snapshot.pk,
        "total_authors": len(autorzy_ids),
        "total_reset": updated_count,
        "optymalizacja_uruchomiona": optymalizacja_uruchomiona,
        "completed_at": datetime.now().isoformat(),
    }


@shared_task(
    base=Singleton,
    unique_on=["uczelnia_id"],
    lock_expiry=3600,
    bind=True,
    time_limit=1800,
)
def reset_all_pins_task(self, uczelnia_id, algorithm_mode="two-phase"):
    """
    Resetuje przypięcia dla wszystkich rekordów 2022-2025 gdzie autor ma dyscyplinę,
    jest zatrudniony i afiliuje.

    Args:
        uczelnia_id: ID uczelni dla której resetować przypięcia
        algorithm_mode: "two-phase" (default) or "single-phase"

    Returns:
        Dictionary z informacją o wykonanych operacjach
    """
    from django.db import transaction

    from bpp.models import (
        Autor_Dyscyplina,
        Uczelnia,
    )
    from snapshot_odpiec.models import SnapshotOdpiec

    uczelnia = Uczelnia.objects.get(pk=uczelnia_id)

    logger.info(f"Starting reset_all_pins_task for {uczelnia}")

    # Update task state
    self.update_state(state="PROGRESS", meta={"step": "collecting", "progress": 10})

    # Pobierz wszystkich autorów którzy mają Autor_Dyscyplina w latach 2022-2025
    # dla dowolnej dyscypliny
    autorzy_ids = set(
        Autor_Dyscyplina.objects.filter(rok__gte=2022, rok__lte=2025)
        .values_list("autor_id", flat=True)
        .distinct()
    )

    logger.info(
        f"Found {len(autorzy_ids)} authors with Autor_Dyscyplina in years 2022-2025"
    )

    # Update task state
    self.update_state(
        state="PROGRESS",
        meta={
            "step": "snapshot",
            "progress": 20,
            "total_authors": len(autorzy_ids),
        },
    )

    with transaction.atomic():
        # Utwórz snapshot przed resetowaniem
        snapshot = SnapshotOdpiec.objects.create(
            owner=None,  # System tworzy snapshot
            comment=f"przed resetem przypięć - wszystkie dyscypliny uczelni {uczelnia}",
        )

        logger.info(
            f"Created snapshot {snapshot.pk} before resetting pins for all disciplines "
            f"(uczelnia: {uczelnia})"
        )

    # Update task state
    self.update_state(
        state="PROGRESS",
        meta={
            "step": "resetting",
            "progress": 30,
            "snapshot_id": snapshot.pk,
            "total_authors": len(autorzy_ids),
        },
    )

    # Reset pins for all models
    count_ciagle, count_zwarte, count_patent, updated_count = _reset_pins_for_authors(
        autorzy_ids, self, snapshot.pk, logger.info
    )

    # Wait for denormalization
    logger.info("Waiting for denormalization...")
    _wait_for_denorm(
        self,
        progress_start=80,
        progress_range=15,
        meta_extra={
            "snapshot_id": snapshot.pk,
            "total_authors": len(autorzy_ids),
            "reset_ciagle": count_ciagle,
            "reset_zwarte": count_zwarte,
            "reset_patent": count_patent,
            "total_reset": updated_count,
        },
        logger_func=logger.info,
    )

    # Run bulk optimization after reset
    logger.info("Starting bulk optimization recalculation after reset")

    liczba_n_raportowane = LiczbaNDlaUczelni.objects.filter(
        uczelnia=uczelnia, liczba_n__gte=12
    ).select_related("dyscyplina_naukowa")

    discipline_count = liczba_n_raportowane.count()
    dyscypliny_ids = list(
        liczba_n_raportowane.values_list("dyscyplina_naukowa_id", flat=True)
    )

    if discipline_count > 0:
        self.update_state(
            state="PROGRESS",
            meta={
                "step": "optimization_start",
                "progress": 95,
                "snapshot_id": snapshot.pk,
                "total_reset": updated_count,
            },
        )

        _run_bulk_optimization(
            self,
            uczelnia,
            dyscypliny_ids,
            discipline_count,
            meta_extra={
                "snapshot_id": snapshot.pk,
                "total_reset": updated_count,
            },
            logger_func=logger.info,
            algorithm_mode=algorithm_mode,
        )

    result = {
        "uczelnia_id": uczelnia_id,
        "uczelnia_nazwa": str(uczelnia),
        "snapshot_id": snapshot.pk,
        "total_authors": len(autorzy_ids),
        "reset_ciagle": count_ciagle,
        "reset_zwarte": count_zwarte,
        "reset_patent": count_patent,
        "total_reset": updated_count,
        "optimizations_recalculated": discipline_count if discipline_count > 0 else 0,
        "completed_at": datetime.now().isoformat(),
    }

    return result
