"""Task odpinania wszystkich sensownych możliwości."""

import logging
from datetime import datetime

from celery import shared_task
from celery_singleton import Singleton

from .helpers import _wait_for_denorm

logger = logging.getLogger(__name__)


@shared_task(
    base=Singleton,
    unique_on=["uczelnia_id"],
    lock_expiry=10800,
    bind=True,
    time_limit=7200,
)
def unpin_all_sensible_task(self, uczelnia_id, min_slot_filled=0.8):  # noqa: C901
    """
    Odpina wszystkie sensowne możliwości odpinania (makes_sense=True),
    czeka na denormalizację i przelicza metryki + analizę unpinning.

    Args:
        uczelnia_id: ID uczelni dla której wykonać odpinanie
        min_slot_filled: Minimalny próg wypełnienia slotów dla ponownej analizy (domyślnie 0.8 = 80%)

    Returns:
        Dictionary z informacją o wykonanych operacjach
    """
    from celery import chain
    from django.contrib.contenttypes.models import ContentType
    from django.db import transaction

    from bpp.models import (
        Patent,
        Patent_Autor,
        Uczelnia,
        Wydawnictwo_Ciagle,
        Wydawnictwo_Ciagle_Autor,
        Wydawnictwo_Zwarte,
        Wydawnictwo_Zwarte_Autor,
    )
    from ewaluacja_metryki.tasks import generuj_metryki_task_parallel
    from ewaluacja_metryki.utils import get_default_rodzaje_autora
    from snapshot_odpiec.models import SnapshotOdpiec

    from ..models import UnpinningOpportunity
    from .unpinning import run_unpinning_after_metrics_wrapper

    uczelnia = Uczelnia.objects.get(pk=uczelnia_id)

    logger.info(f"Starting unpin_all_sensible_task for {uczelnia}")

    # Update task state
    self.update_state(state="PROGRESS", meta={"step": "collecting", "progress": 5})

    # Get content types
    ct_ciagle = ContentType.objects.get_for_model(Wydawnictwo_Ciagle)
    ct_zwarte = ContentType.objects.get_for_model(Wydawnictwo_Zwarte)
    ct_patent = ContentType.objects.get_for_model(Patent)

    # Query all sensible unpinning opportunities for this uczelnia
    opportunities = UnpinningOpportunity.objects.filter(
        uczelnia=uczelnia, makes_sense=True
    ).select_related("autor_could_benefit", "dyscyplina_naukowa")

    total_opportunities = opportunities.count()

    logger.info(f"Found {total_opportunities} sensible unpinning opportunities")

    if total_opportunities == 0:
        logger.info("No sensible opportunities found, task completed")
        return {
            "uczelnia_id": uczelnia_id,
            "uczelnia_nazwa": str(uczelnia),
            "total_opportunities": 0,
            "unpinned_count": 0,
            "message": "Brak sensownych możliwości odpinania",
            "completed_at": datetime.now().isoformat(),
        }

    # Update task state
    self.update_state(
        state="PROGRESS",
        meta={
            "step": "snapshot",
            "progress": 10,
            "total_opportunities": total_opportunities,
        },
    )

    with transaction.atomic():
        # Create snapshot before unpinning
        snapshot = SnapshotOdpiec.objects.create(
            owner=None,  # System tworzy snapshot
            comment=f"przed odpięciem wszystkich sensownych możliwości - uczelnia {uczelnia}",
        )

        logger.info(
            f"Created snapshot {snapshot.pk} before unpinning all sensible opportunities "
            f"(uczelnia: {uczelnia})"
        )

    # Update task state
    self.update_state(
        state="PROGRESS",
        meta={
            "step": "unpinning",
            "progress": 20,
            "snapshot_id": snapshot.pk,
            "total_opportunities": total_opportunities,
        },
    )

    # Unpin all sensible opportunities
    unpinned_count = 0
    unpinned_ciagle = 0
    unpinned_zwarte = 0
    unpinned_patent = 0

    for idx, opportunity in enumerate(opportunities, 1):
        try:
            content_type_id = opportunity.rekord_id[0]
            object_id = opportunity.rekord_id[1]
            autor = opportunity.autor_could_benefit
            dyscyplina = opportunity.dyscyplina_naukowa

            # Determine which model to use based on content_type_id
            if content_type_id == ct_ciagle.pk:
                # Wydawnictwo_Ciagle_Autor
                updated = Wydawnictwo_Ciagle_Autor.objects.filter(
                    rekord_id=object_id, autor=autor, dyscyplina_naukowa=dyscyplina
                ).update(przypieta=False)
                unpinned_ciagle += updated
            elif content_type_id == ct_zwarte.pk:
                # Wydawnictwo_Zwarte_Autor
                updated = Wydawnictwo_Zwarte_Autor.objects.filter(
                    rekord_id=object_id, autor=autor, dyscyplina_naukowa=dyscyplina
                ).update(przypieta=False)
                unpinned_zwarte += updated
            elif content_type_id == ct_patent.pk:
                # Patent_Autor
                updated = Patent_Autor.objects.filter(
                    rekord_id=object_id, autor=autor, dyscyplina_naukowa=dyscyplina
                ).update(przypieta=False)
                unpinned_patent += updated
            else:
                logger.warning(
                    f"Unknown content_type_id {content_type_id} for opportunity {opportunity.pk}"
                )
                continue

            unpinned_count += updated

            if idx % 10 == 0:
                # Update progress every 10 opportunities
                progress = 20 + (idx / total_opportunities) * 30
                self.update_state(
                    state="PROGRESS",
                    meta={
                        "step": "unpinning",
                        "progress": progress,
                        "snapshot_id": snapshot.pk,
                        "total_opportunities": total_opportunities,
                        "processed": idx,
                        "unpinned_count": unpinned_count,
                    },
                )

        except Exception as e:
            logger.error(
                f"Failed to unpin opportunity {opportunity.pk}: {e}", exc_info=True
            )

    logger.info(
        f"Unpinning complete. Total unpinned: {unpinned_count} "
        f"(Ciągłe: {unpinned_ciagle}, Zwarte: {unpinned_zwarte}, Patent: {unpinned_patent})"
    )

    # Update task state
    self.update_state(
        state="PROGRESS",
        meta={
            "step": "waiting_denorm",
            "progress": 50,
            "snapshot_id": snapshot.pk,
            "total_opportunities": total_opportunities,
            "unpinned_count": unpinned_count,
            "unpinned_ciagle": unpinned_ciagle,
            "unpinned_zwarte": unpinned_zwarte,
            "unpinned_patent": unpinned_patent,
        },
    )

    # Wait for denormalization
    logger.info("Waiting for denormalization...")
    _wait_for_denorm(
        self,
        progress_start=50,
        progress_range=20,
        meta_extra={
            "snapshot_id": snapshot.pk,
            "total_opportunities": total_opportunities,
            "unpinned_count": unpinned_count,
            "unpinned_ciagle": unpinned_ciagle,
            "unpinned_zwarte": unpinned_zwarte,
            "unpinned_patent": unpinned_patent,
        },
        logger_func=logger.info,
    )

    # Update task state
    self.update_state(
        state="PROGRESS",
        meta={
            "step": "recalculating_metrics",
            "progress": 70,
            "snapshot_id": snapshot.pk,
            "total_opportunities": total_opportunities,
            "unpinned_count": unpinned_count,
            "message": "Uruchamianie przeliczania metryk...",
        },
    )

    # Chain: metrics recalculation -> unpinning analysis
    logger.info("Starting metrics recalculation and unpinning analysis")

    workflow = chain(
        generuj_metryki_task_parallel.s(
            rodzaje_autora=get_default_rodzaje_autora(),
            nadpisz=True,
            przelicz_liczbe_n=True,
        ),
        run_unpinning_after_metrics_wrapper.s(
            uczelnia_id=uczelnia.pk, dyscyplina_id=None, min_slot_filled=min_slot_filled
        ),
    )

    workflow_result = workflow.apply_async()

    logger.info(
        f"Metrics + unpinning analysis workflow started with task_id: {workflow_result.id}"
    )

    # Wait for workflow to complete with progress updates
    from time import sleep

    max_wait = 1800  # Max 30 minutes
    waited = 0
    check_interval = 10  # Check every 10 seconds

    while not workflow_result.ready() and waited < max_wait:
        sleep(check_interval)
        waited += check_interval

        # Calculate progress: 70-95% for this phase
        progress = min(70 + (waited / max_wait * 25), 95)

        # Try to get info about current workflow step
        # workflow_result.id is the ID of the LAST task in the chain (unpinning analysis)
        current_info = workflow_result.info if workflow_result.info else {}

        # Determine which phase we're in based on task info
        if isinstance(current_info, dict):
            current_step = current_info.get("step", "workflow_running")
        else:
            current_step = "workflow_running"

        self.update_state(
            state="PROGRESS",
            meta={
                "step": "workflow_running",
                "substep": current_step,
                "progress": progress,
                "snapshot_id": snapshot.pk,
                "total_opportunities": total_opportunities,
                "unpinned_count": unpinned_count,
                "message": "Przeliczanie metryk i analizy unpinning w trakcie...",
                "waited_seconds": waited,
            },
        )

        logger.info(
            f"Waiting for workflow completion... {waited}s elapsed, progress: {progress:.1f}%"
        )

    # Check if workflow completed successfully
    if workflow_result.ready():
        if workflow_result.successful():
            workflow_final_result = workflow_result.result
            logger.info(f"Workflow completed successfully: {workflow_final_result}")

            # Update to 100%
            self.update_state(
                state="PROGRESS",
                meta={
                    "step": "completed",
                    "progress": 100,
                    "snapshot_id": snapshot.pk,
                    "total_opportunities": total_opportunities,
                    "unpinned_count": unpinned_count,
                    "message": "Proces zakończony pomyślnie!",
                },
            )
        else:
            # Workflow failed
            error_info = str(workflow_result.info)
            logger.error(f"Workflow failed: {error_info}")
            raise Exception(
                f"Workflow przeliczania metryk i analizy nie powiódł się: {error_info}"
            )
    else:
        # Timeout
        logger.warning(f"Workflow timeout after {waited}s")
        raise Exception(
            f"Timeout: Workflow przeliczania metryk i analizy nie zakończył się w ciągu {max_wait}s"
        )

    result = {
        "uczelnia_id": uczelnia_id,
        "uczelnia_nazwa": str(uczelnia),
        "snapshot_id": snapshot.pk,
        "total_opportunities": total_opportunities,
        "unpinned_count": unpinned_count,
        "unpinned_ciagle": unpinned_ciagle,
        "unpinned_zwarte": unpinned_zwarte,
        "unpinned_patent": unpinned_patent,
        "workflow_task_id": workflow_result.id,
        "workflow_result": workflow_final_result,
        "completed_at": datetime.now().isoformat(),
    }

    logger.info(f"unpin_all_sensible_task completed: {result}")

    return result
