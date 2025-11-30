"""Publication integration operations for PBN integrator."""

from __future__ import annotations

import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import TYPE_CHECKING

from bpp.models import Rekord
from pbn_api.models import OswiadczenieInstytucji, Publication
from pbn_integrator.utils.multiprocessing_utils import (
    _bede_uzywal_bazy_danych_z_multiprocessing_z_django,
    initialize_pool,
    split_list,
    wait_for_results,
)

if TYPE_CHECKING:
    pass


def zweryfikuj_lub_stworz_match(elem, bpp_rekord):
    """Verify or create a match between PBN publication and BPP record.

    Args:
        elem: PBN Publication object.
        bpp_rekord: BPP record.
    """
    if bpp_rekord is not None:
        if bpp_rekord.pbn_uid_id is not None and bpp_rekord.pbn_uid_id != elem.pk:
            print(
                f"\r\n*** Rekord BPP {bpp_rekord} {bpp_rekord.rok} ma już PBN UID {bpp_rekord.pbn_uid_id}, "
                f"ale i pasuje też do {elem} PBN UID {elem.pk}"
            )
            return

        if bpp_rekord.pbn_uid_id is None:
            p = bpp_rekord.original
            p.pbn_uid_id = elem.pk
            p.save(update_fields=["pbn_uid_id"])


def _integruj_single_part(ids):
    """Integrate a batch of publication IDs.

    Args:
        ids: List of publication IDs.
    """
    for _id in ids:
        try:
            elem = Publication.objects.get(pk=_id)
        except Publication.DoesNotExist as e:
            print(f"Brak publikacji o ID {_id}")
            raise e
        p = elem.matchuj_do_rekordu_bpp()
        zweryfikuj_lub_stworz_match(elem, p)


def _integruj_publikacje(
    pubs,
    disable_multiprocessing=False,
    skip_pages=0,
    label="_integruj_publikacje",
    callback=None,
):
    """Integrate publications using multiprocessing.

    Args:
        pubs: List of publication IDs.
        disable_multiprocessing: If True, runs in single-process mode.
        skip_pages: Number of batches to skip.
        label: Label for progress display.
        callback: Optional callback for progress updates.
    """
    _bede_uzywal_bazy_danych_z_multiprocessing_z_django()
    pool = initialize_pool()

    BATCH_SIZE = 128
    results = []
    total_batches = len(pubs) // BATCH_SIZE + (1 if len(pubs) % BATCH_SIZE else 0)

    for no, elem in enumerate(split_list(pubs, BATCH_SIZE)):
        if no < skip_pages:
            continue

        if disable_multiprocessing:
            _integruj_single_part(elem)
            print(f"{label} {no} of {total_batches}...", end="\r")
            sys.stdout.flush()

            # Update callback if provided
            if callback:
                callback.update(
                    no + 1,
                    total_batches,
                    f"Integrowanie publikacji: batch {no + 1}/{total_batches}",
                )
        else:
            result = pool.apply_async(_integruj_single_part, args=(elem,))
            results.append(result)

    wait_for_results(pool, results, label=label)


def _integruj_publikacje_threaded(  # noqa: C901
    pubs,
    disable_threading=False,
    skip_pages=0,
    label="_integruj_publikacje",
    callback=None,
    max_workers=None,
):
    """Thread-based implementation of _integruj_publikacje with proper thread safety.

    This implementation uses threads instead of processes, which is more efficient
    for I/O-bound operations like database queries and network requests.

    Args:
        pubs: List of publication IDs to process.
        disable_threading: If True, runs in single-threaded mode.
        skip_pages: Number of batches to skip.
        label: Label for progress display.
        callback: Optional callback for progress updates.
        max_workers: Maximum number of worker threads (default: CPU count * 3/4).

    Thread Safety Measures:
        - Each thread gets its own database connection.
        - Print statements are protected by locks.
        - Callback updates are synchronized.
        - Progress counters are thread-safe.
    """
    import threading

    # Thread-safe locks for shared resources
    _print_lock = threading.Lock()
    _callback_lock = threading.Lock()
    _progress_lock = threading.Lock()

    BATCH_SIZE = 128
    total_batches = len(pubs) // BATCH_SIZE + (1 if len(pubs) % BATCH_SIZE else 0)
    completed_batches = [skip_pages]  # Use list for mutable integer in closure

    def _thread_safe_integruj_single_part(batch_data):
        """Thread-safe wrapper for _integruj_single_part."""
        batch_ids, batch_no = batch_data

        # Each thread needs its own database connection
        from django.db import close_old_connections

        close_old_connections()

        try:
            # Process the batch
            _integruj_single_part(batch_ids)

            # Thread-safe progress update
            with _progress_lock:
                completed_batches[0] += 1
                current_progress = completed_batches[0]

            # Thread-safe print
            with _print_lock:
                print(f"{label} {current_progress} of {total_batches}...", end="\r")
                sys.stdout.flush()

            # Thread-safe callback update
            if callback:
                with _callback_lock:
                    callback.update(
                        current_progress,
                        total_batches,
                        f"Integrowanie publikacji: batch {current_progress}/{total_batches}",
                    )

            return batch_no, True, None

        except Exception as e:
            # Log errors with thread safety
            with _print_lock:
                print(f"\nError in batch {batch_no}: {str(e)}")
            return batch_no, False, str(e)

        finally:
            # Clean up database connections
            close_old_connections()

    # Prepare batches with their indices
    batches = []
    for no, batch_ids in enumerate(split_list(pubs, BATCH_SIZE)):
        if no < skip_pages:
            continue
        batches.append((batch_ids, no))

    if disable_threading:
        # Single-threaded execution
        for batch_ids, batch_no in batches:
            _thread_safe_integruj_single_part((batch_ids, batch_no))
    else:
        # Multi-threaded execution
        if max_workers is None:
            # Default to 3/4 of CPU cores for threads (more than processes since threads are lighter)
            max_workers = max(1, os.cpu_count() * 3 // 4)

        # Use ThreadPoolExecutor for better thread management
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all tasks
            futures = {
                executor.submit(
                    _thread_safe_integruj_single_part, batch_data
                ): batch_data[1]
                for batch_data in batches
            }

            # Process results as they complete
            errors = []
            for future in as_completed(futures):
                batch_no = futures[future]
                try:
                    batch_no, success, error = future.result()
                    if not success and error:
                        errors.append(f"Batch {batch_no}: {error}")
                except Exception as e:
                    with _print_lock:
                        print(f"\nUnexpected error in batch {batch_no}: {str(e)}")
                    errors.append(f"Batch {batch_no}: {str(e)}")

            # Report any errors at the end
            if errors:
                with _print_lock:
                    print(f"\n{len(errors)} batches failed during processing:")
                    for error in errors[:5]:  # Show first 5 errors
                        print(f"  - {error}")
                    if len(errors) > 5:
                        print(f"  ... and {len(errors) - 5} more")

    # Final cleanup
    with _print_lock:
        print(
            f"\n{label} completed: {completed_batches[0]}/{total_batches} batches processed"
        )
        sys.stdout.flush()


def integruj_wszystkie_publikacje(
    disable_multiprocessing=False,
    ignore_already_matched=False,
    skip_pages=0,
    use_threads=False,
    callback=None,
):
    """Integrate all publications from PBN with BPP.

    Args:
        disable_multiprocessing: If True, runs in single-process/thread mode.
        ignore_already_matched: If True, skips publications already matched.
        skip_pages: Number of batches to skip.
        use_threads: If True, uses threaded implementation instead of multiprocessing.
        callback: Optional progress callback.
    """
    pubs = Publication.objects.all()

    if ignore_already_matched:
        pubs = pubs.exclude(
            pk__in=Rekord.objects.exclude(pbn_uid_id=None)
            .values_list("pbn_uid_id", flat=True)
            .distinct()
        )

    pubs = pubs.order_by("-pk")
    pubs = list(pubs.values_list("pk", flat=True).distinct())

    if use_threads:
        return _integruj_publikacje_threaded(
            pubs,
            disable_threading=disable_multiprocessing,
            skip_pages=skip_pages,
            callback=callback,
        )
    else:
        return _integruj_publikacje(
            pubs,
            disable_multiprocessing=disable_multiprocessing,
            skip_pages=skip_pages,
            callback=callback,
        )


def integruj_publikacje_instytucji(
    skip_pages=0,
    callback=None,
    use_threads=False,
):
    """Integrate institution publications.

    Args:
        skip_pages: Number of batches to skip.
        callback: Optional callback function for progress tracking.
        use_threads: If True, uses the threaded implementation instead of multiprocessing.
    """
    pubs = (
        OswiadczenieInstytucji.objects.all()
        .values_list("publicationId_id", flat=True)
        .order_by("-pk")
        .distinct()
    )

    if use_threads:
        return _integruj_publikacje_threaded(
            pubs,
            skip_pages=skip_pages,
            callback=callback,
        )
    else:
        # Zostawiamy wersje z multiprocessing ALE wyłączamy to
        return _integruj_publikacje(
            pubs,
            disable_multiprocessing=True,
            skip_pages=skip_pages,
            callback=callback,
        )
