"""Journal/source handling for PBN importer."""

import logging
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

import rollbar
from django.db import DataError, IntegrityError, close_old_connections, transaction
from django.db.models import Subquery

from bpp import const
from bpp.models import (
    Dyscyplina_Naukowa,
    Dyscyplina_Zrodla,
    Punktacja_Zrodla,
    Rodzaj_Zrodla,
    Zrodlo,
)
from bpp.util import pbar
from pbn_api.models import Journal
from pbn_integrator.utils import integruj_zrodla

logger = logging.getLogger(__name__)

MAX_SLUG_RETRIES = 10


def _real_issn(value):
    """Odfiltruj syntetyczny placeholder PBN z pola ISSN.

    PBN dla czasopism bez ISSN podsyła wewnętrzny identyfikator w formie
    ``xpbn-<uuid>`` (41 znaków), który nie jest ISSN-em, a do tego nie mieści
    się w ``Zrodlo.issn`` (max_length=32) — dosłowny zapis wywalał
    ``DataError: value too long``. Traktujemy go z powrotem jako *brak* ISSN.
    """
    value = (value or "").strip()
    return "" if value.startswith("xpbn-") else value


def dopisz_jedno_zrodlo(pbn_journal, rodzaj_periodyk, dyscypliny_cache):
    """Process single journal - re-entrant, can be interrupted.

    Uses retry mechanism to handle slug collisions in parallel execution.
    """
    assert pbn_journal.rekord_w_bpp() is None

    cv = pbn_journal.current_version["object"]

    # Retry loop for slug collision handling
    zrodlo: Zrodlo
    for attempt in range(MAX_SLUG_RETRIES):
        try:
            with transaction.atomic():
                zrodlo = Zrodlo.objects.create(
                    nazwa=cv.get("title") or "",
                    skrot=cv.get("title") or "",
                    issn=_real_issn(cv.get("issn")),
                    e_issn=_real_issn(cv.get("eissn")),
                    pbn_uid=pbn_journal,
                    rodzaj=rodzaj_periodyk,
                )
            break  # Success - exit retry loop
        except IntegrityError as e:
            if "bpp_zrodlo_slug_key" in str(e) and attempt < MAX_SLUG_RETRIES - 1:
                # Slug collision - retry will generate a new slug
                time.sleep(0.5)
                continue
            raise  # Other IntegrityError or max retries exceeded
    else:
        raise RuntimeError(f"Failed to create Zrodlo after {MAX_SLUG_RETRIES} retries")

    # Bulk create points
    punktacje = [
        Punktacja_Zrodla(zrodlo=zrodlo, rok=rok, punkty_kbn=value.get("points"))
        for rok, value in cv.get("points", {}).items()
        if value.get("accepted")
    ]
    if punktacje:
        Punktacja_Zrodla.objects.bulk_create(punktacje, ignore_conflicts=True)

    # Bulk create disciplines for all years
    dyscypliny_zrodel = []
    for discipline in cv.get("disciplines", []):
        nazwa = discipline.get("name")
        dyscyplina = dyscypliny_cache.get(nazwa)
        if not dyscyplina:
            raise DataError(f"Brak dyscypliny o nazwie {nazwa}")

        for rok in range(const.PBN_MIN_ROK, const.PBN_MAX_ROK + 1):
            dyscypliny_zrodel.append(
                Dyscyplina_Zrodla(zrodlo=zrodlo, rok=rok, dyscyplina=dyscyplina)
            )

    if dyscypliny_zrodel:
        Dyscyplina_Zrodla.objects.bulk_create(dyscypliny_zrodel, ignore_conflicts=True)


def _process_journal_thread_safe(journal_id, rodzaj_periodyk, dyscypliny_cache):
    """Thread-safe wrapper for processing a single journal.

    Receives only the journal *id* and loads the full ``Journal`` (with its
    heavy ``versions`` JSON) here, inside the worker thread, so the object is
    freed as soon as the thread is done with it. Keeping at most
    ``max_workers`` journals resident at once is what bounds peak memory.
    """
    close_old_connections()
    try:
        pbn_journal = Journal.objects.get(pk=journal_id)
        dopisz_jedno_zrodlo(pbn_journal, rodzaj_periodyk, dyscypliny_cache)
        return {"success": True, "journal_id": journal_id, "error": None}
    except Exception as e:
        # Catch-all w wątku roboczym — błąd źródła nie może zniknąć po cichu.
        # Pełny traceback do logów + Rollbar; status i tak wraca do agregatora.
        # Odwołujemy się do journal_id (nie pbn_journal.pk) — gdy Journal.get()
        # padnie, pbn_journal jest niezdefiniowany; journal_id jest zawsze znany.
        logger.exception("Błąd importu źródła PBN %s", journal_id)
        rollbar.report_exc_info(
            sys.exc_info(),
            extra_data={"journal_id": journal_id, "phase": "dopisz_jedno_zrodlo"},
        )
        return {"success": False, "journal_id": journal_id, "error": str(e)}
    finally:
        close_old_connections()


def importuj_zrodla(max_workers=None, disable_threading=False):
    """Import sources from PBN - parallelized, re-entrant, can be interrupted."""
    integruj_zrodla()

    # Cache lookups ONCE (2 queries instead of N + N*M)
    rodzaj_periodyk = Rodzaj_Zrodla.objects.get(nazwa="periodyk")
    dyscypliny_cache = {d.nazwa: d for d in Dyscyplina_Naukowa.objects.all()}

    # Filter already imported - supports re-entrancy.
    # Gather only primary keys, never the full objects: each ``Journal`` row
    # carries a large ``versions`` JSON blob, so materializing the whole table
    # at once is what used to blow up memory. We load each journal lazily,
    # inside the worker, where it is freed right after processing.
    imported_ids = Zrodlo.objects.filter(pbn_uid__isnull=False).values_list(
        "pbn_uid_id", flat=True
    )
    journal_ids = list(
        Journal.objects.filter(status="ACTIVE")
        .exclude(pk__in=Subquery(imported_ids))
        .values_list("pk", flat=True)
    )

    if not journal_ids:
        return

    # Determine thread count
    if max_workers is None:
        max_workers = max(1, (os.cpu_count() or 4) * 3 // 4)

    if disable_threading or max_workers == 1:
        # Sequential fallback - load one journal at a time.
        for journal_id in pbar(journal_ids, label="Dopisywanie źródeł MNISW..."):
            dopisz_jedno_zrodlo(
                Journal.objects.get(pk=journal_id),
                rodzaj_periodyk,
                dyscypliny_cache,
            )
    else:
        # Parallel execution
        errors = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    _process_journal_thread_safe,
                    journal_id,
                    rodzaj_periodyk,
                    dyscypliny_cache,
                ): journal_id
                for journal_id in journal_ids
            }

            for future in pbar(
                as_completed(futures),
                count=len(futures),
                label="Dopisywanie źródeł MNISW...",
            ):
                result = future.result()
                if not result["success"]:
                    errors.append(f"Journal {result['journal_id']}: {result['error']}")

        if errors:
            print(f"\n{len(errors)} errors occurred:")
            for err in errors[:10]:  # Show first 10 errors
                print(f"  - {err}")
            if len(errors) > 10:
                print(f"  ... and {len(errors) - 10} more")
