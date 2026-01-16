"""Journal/source handling for PBN importer."""

import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

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

MAX_SLUG_RETRIES = 10


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
                    issn=cv.get("issn") or "",
                    e_issn=cv.get("eissn") or "",
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


def _process_journal_thread_safe(pbn_journal, rodzaj_periodyk, dyscypliny_cache):
    """Thread-safe wrapper for processing a single journal."""
    close_old_connections()
    try:
        dopisz_jedno_zrodlo(pbn_journal, rodzaj_periodyk, dyscypliny_cache)
        return {"success": True, "journal_id": pbn_journal.pk, "error": None}
    except Exception as e:
        return {"success": False, "journal_id": pbn_journal.pk, "error": str(e)}
    finally:
        close_old_connections()


def importuj_zrodla(max_workers=None, disable_threading=False):
    """Import sources from PBN - parallelized, re-entrant, can be interrupted."""
    integruj_zrodla()

    # Cache lookups ONCE (2 queries instead of N + N*M)
    rodzaj_periodyk = Rodzaj_Zrodla.objects.get(nazwa="periodyk")
    dyscypliny_cache = {d.nazwa: d for d in Dyscyplina_Naukowa.objects.all()}

    # Filter already imported - supports re-entrancy
    imported_ids = Zrodlo.objects.filter(pbn_uid__isnull=False).values_list(
        "pbn_uid_id", flat=True
    )
    journals = list(
        Journal.objects.filter(status="ACTIVE").exclude(pk__in=Subquery(imported_ids))
    )

    if not journals:
        return

    # Determine thread count
    if max_workers is None:
        max_workers = max(1, (os.cpu_count() or 4) * 3 // 4)

    if disable_threading or max_workers == 1:
        # Sequential fallback
        for journal in pbar(journals, label="Dopisywanie źródeł MNISW..."):
            dopisz_jedno_zrodlo(journal, rodzaj_periodyk, dyscypliny_cache)
    else:
        # Parallel execution
        errors = []
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(
                    _process_journal_thread_safe,
                    journal,
                    rodzaj_periodyk,
                    dyscypliny_cache,
                ): journal
                for journal in journals
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
