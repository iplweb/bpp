"""Multiprocessing and threading utilities for PBN integrator."""

from __future__ import annotations

import multiprocessing
import os

from bpp.util import pbar
from pbn_integrator.utils.constants import CPU_COUNT, DEFAULT_CONTEXT


def _bede_uzywal_bazy_danych_z_multiprocessing_z_django():
    """Prepare Django database connections for use with multiprocessing."""
    from django.db import close_old_connections, connections

    close_old_connections()
    connections.close_all()


def _init():
    """Initialize Django in a worker process."""
    import django

    django.setup()


def initialize_pool(multipler=1):
    """Initialize a multiprocessing pool.

    Args:
        multipler: Multiplier for CPU count.

    Returns:
        A multiprocessing Pool object.
    """
    if CPU_COUNT == "auto":
        cpu_count = os.cpu_count() * 3 // 4
        if cpu_count < 1:
            cpu_count = 1

        cpu_count = cpu_count * multipler
        if cpu_count < 1:
            cpu_count = 1

    elif CPU_COUNT == "single":
        cpu_count = 1
    else:
        raise NotImplementedError(f"CPU_COUNT = {CPU_COUNT}")

    return multiprocessing.get_context(DEFAULT_CONTEXT).Pool(
        cpu_count, initializer=_init
    )


def wait_for_results(pool, results, label="Progress..."):
    """Wait for all multiprocessing results to complete.

    Args:
        pool: The multiprocessing pool.
        results: List of AsyncResult objects.
        label: Label for progress bar.
    """
    for elem in pbar(results, count=len(results), label=label):
        elem.get()
    pool.close()
    pool.join()


def split_list(lst, n):
    """Split a list into chunks of size n.

    Args:
        lst: List to split.
        n: Chunk size.

    Yields:
        Chunks of the list.
    """
    for i in range(0, len(lst), n):
        yield lst[i : i + n]
