"""Source scoring (points and disciplines) synchronization for PBN import."""

import logging
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

from django.db import close_old_connections
from tqdm import tqdm

from bpp.models import Dyscyplina_Naukowa, Punktacja_Zrodla, Zrodlo

from .base import CancelledException, ImportStepBase

logger = logging.getLogger("pbn_import")


def _sync_single_source(zrodlo_id, min_rok, dyscypliny_dict):
    """Synchronize points and disciplines for a single source.

    This function is designed to be called from a thread pool worker.

    Args:
        zrodlo_id: ID of the Zrodlo to synchronize.
        min_rok: Minimum year for point data.
        dyscypliny_dict: Dict mapping discipline codes to IDs.

    Returns:
        Tuple of (zrodlo_id, success, error_message).
    """
    try:
        # Ensure fresh DB connection in thread
        close_old_connections()

        zrodlo = Zrodlo.objects.select_related("pbn_uid").get(pk=zrodlo_id)

        # Import points
        ostatni_rok = _import_points_for_zrodlo(zrodlo, min_rok)

        # Import disciplines
        _import_disciplines_for_zrodlo(zrodlo, ostatni_rok, dyscypliny_dict)

        return (zrodlo_id, True, None)

    except Exception as e:
        return (zrodlo_id, False, str(e))


def _import_points_for_zrodlo(zrodlo, min_rok):
    """Import points for a source and return the last year with data."""
    points = zrodlo.pbn_uid.value("object", "points", return_none=True) or {}
    ostatni_rok = None

    for rok in points:
        if int(rok) < min_rok:
            continue
        ostatni_rok = int(rok)
        punkty = points[rok].get("points")
        if punkty is not None:
            _update_or_create_punktacja(zrodlo, rok, punkty)

    return ostatni_rok


def _update_or_create_punktacja(zrodlo, rok, punkty):
    """Update or create Punktacja_Zrodla for given year."""
    try:
        pzr = zrodlo.punktacja_zrodla_set.get(rok=rok)
        if pzr.punkty_kbn != punkty:
            pzr.punkty_kbn = punkty
            pzr.save()
    except Punktacja_Zrodla.DoesNotExist:
        zrodlo.punktacja_zrodla_set.create(punkty_kbn=punkty, rok=rok)


def _import_disciplines_for_zrodlo(zrodlo, ostatni_rok, dyscypliny_dict):
    """Import disciplines for a source."""
    if ostatni_rok is None:
        return

    disciplines = zrodlo.pbn_uid.value("object", "disciplines", return_none=True)
    if not disciplines:
        return

    # Usuń stare i dodaj nowe
    zrodlo.dyscyplina_zrodla_set.all().delete()

    for disc_dict in disciplines:
        code = disc_dict.get("code") if isinstance(disc_dict, dict) else disc_dict
        if not code:
            continue
        code = str(code)
        kod_dyscypliny = f"{int(code[0])}.{int(code[1:])}"

        if kod_dyscypliny not in dyscypliny_dict:
            continue

        zrodlo.dyscyplina_zrodla_set.get_or_create(
            dyscyplina_id=dyscypliny_dict[kod_dyscypliny],
            rok=ostatni_rok,
        )


class SourceScoringImporter(ImportStepBase):
    """Synchronizes points and disciplines for sources with PBN data."""

    step_name = "source_scoring_import"
    step_description = "Synchronizacja punktów i dyscyplin źródeł"

    def __init__(self, session, client=None, min_rok=2017, max_workers=None):
        super().__init__(session, client)
        self.min_rok = min_rok
        self.max_workers = (
            max_workers if max_workers is not None else (os.cpu_count() or 8)
        )

    def run(self):
        """Synchronize points and disciplines for all sources with pbn_uid."""
        # Build dict mapping discipline code to ID (not full object - for thread safety)
        dyscypliny_dict = {x.kod: x.pk for x in Dyscyplina_Naukowa.objects.all()}

        # Get source IDs to process
        zrodlo_ids = list(
            Zrodlo.objects.exclude(pbn_uid_id=None).values_list("pk", flat=True)
        )
        total = len(zrodlo_ids)

        if total == 0:
            self.log("info", "Brak źródeł z pbn_uid do synchronizacji")
            return {"synchronized": 0, "failed": 0}

        self.log(
            "info",
            f"Synchronizacja punktów i dyscyplin dla {total} źródeł "
            f"({self.max_workers} wątków)...",
        )
        self.update_progress(0, total, "Synchronizacja źródeł")

        # Create progress callback
        subtask_callback = self.create_subtask_progress("Synchronizacja źródeł")

        synchronized = 0
        failed = 0
        errors = []

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all tasks
            futures = {
                executor.submit(
                    _sync_single_source,
                    zrodlo_id,
                    self.min_rok,
                    dyscypliny_dict,
                ): zrodlo_id
                for zrodlo_id in zrodlo_ids
            }

            # Process results as they complete with tqdm progress bar
            for i, future in enumerate(
                tqdm(
                    as_completed(futures),
                    total=total,
                    desc="Synchronizacja źródeł",
                    unit="src",
                ),
                1,
            ):
                # Check cancellation periodically
                if i % 100 == 0:
                    if self.check_cancelled():
                        # Cancel remaining futures
                        for f in futures:
                            f.cancel()
                        raise CancelledException("Import został anulowany")

                zrodlo_id, success, error = future.result()

                if success:
                    synchronized += 1
                else:
                    failed += 1
                    errors.append(f"Źródło {zrodlo_id}: {error}")

                # Update session progress callback
                desc = f"OK: {synchronized}, błędów: {failed}"
                subtask_callback.update(i, total, desc)

        self.clear_subtask_progress()
        self.update_progress(total, total, "Zakończono synchronizację")

        # Log errors (first 10)
        for error in errors[:10]:
            self.log("warning", error)
        if len(errors) > 10:
            self.log("warning", f"... i {len(errors) - 10} kolejnych błędów")

        self.log("success", f"Zsynchronizowano {synchronized} źródeł, {failed} błędów")
        return {"synchronized": synchronized, "failed": failed}
