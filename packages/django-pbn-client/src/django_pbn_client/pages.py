"""Concurrent page download services for PBN iterators."""

from __future__ import annotations

import multiprocessing
from collections.abc import Callable, Iterable
from multiprocessing.dummy import Pool as ThreadPool
from typing import TypeVar

from django import setup as django_setup
from django.db import close_old_connections, connections
from pbn_client.exceptions import HttpException

from django_pbn_client.persistence import upsert_pbn_object

PageResult = TypeVar("PageResult")
PageProgressWrapper = Callable[
    [Iterable[PageResult], int | None, str],
    Iterable[PageResult],
]


def simple_page_getter(
    client,
    data,
    repeat_on_failure=False,
    skip_page_on_failure=False,
):
    """Yield paginator pages sequentially with optional HTTP 500 retries."""
    del client

    for page_number in range(data.total_pages):
        while True:
            try:
                yield data.fetch_page(page_number)
                break
            except HttpException as error:
                if skip_page_on_failure:
                    break
                if not repeat_on_failure or error.status_code != 500:
                    raise


class ThreadedPageGetter:
    """Fetch and process individual pages supplied by a PBN paginator."""

    def __init__(self, max_workers=None, model_class=None):
        self.max_workers = max_workers
        self.model_class = model_class
        if model_class is not None:
            self.pbn_api_klass = model_class
        self.client = None
        self.data = None

    def pool_init(self, client, data):
        django_setup()
        self.client = client
        self.data = data

    def process_element(self, element):
        raise NotImplementedError

    def get_single_page(self, page_number):
        for element in self.data.fetch_page(page_number):
            self.process_element(element)


class ThreadedModelSaver(ThreadedPageGetter):
    """Page getter that atomically stores each element in a Django model."""

    save_function = staticmethod(upsert_pbn_object)

    def process_element(self, element):
        self.save_function(element, self.pbn_api_klass)


# The old name describes the upstream PBN storage, not the local database.
# Keep it as an alias for applications migrating from BPP.
ThreadedMongoDBSaver = ThreadedModelSaver


_process_getter = None


def _initialize_process_getter(getter, client, data):
    """Initialize the getter instance owned by one worker process."""
    global _process_getter

    getter.pool_init(client, data)
    _process_getter = getter


def _get_single_page_in_process(page_number):
    """Dispatch a page through the getter initialized in this process."""
    return _process_getter.get_single_page(page_number)


def _make_getter(getter_class, workers):
    try:
        return getter_class(max_workers=workers)
    except TypeError:
        # Compatibility with existing getter classes that predate max_workers.
        return getter_class()


def _make_pool(method, workers, getter, client, data):
    if method == "threads":
        pool = ThreadPool(
            processes=workers,
            initializer=getter.pool_init,
            initargs=(client, data),
        )
        return pool, getter.get_single_page

    if method == "processes":
        close_old_connections()
        connections.close_all()
        pool = multiprocessing.get_context("fork").Pool(
            processes=workers,
            initializer=_initialize_process_getter,
            initargs=(getter, client, data),
        )
        return pool, _get_single_page_in_process

    raise ValueError(f"Unsupported page download method: {method!r}")


def download_pages(
    client,
    data,
    *,
    getter_class=ThreadedPageGetter,
    workers=12,
    label="getting...",
    method="threads",
    progress: PageProgressWrapper | None = None,
):
    """Fetch all paginator pages concurrently and process their elements."""
    getter = _make_getter(getter_class, workers)
    effective_workers = getattr(getter, "max_workers", None) or workers
    pool, get_single_page = _make_pool(
        method,
        effective_workers,
        getter,
        client,
        data,
    )

    try:
        completed_pages = pool.imap_unordered(
            get_single_page,
            range(data.total_pages),
        )
        if progress is not None:
            completed_pages = progress(
                completed_pages,
                data.total_pages,
                label,
            )
        for _completed_page in completed_pages:
            pass
    except BaseException:
        pool.terminate()
        raise
    else:
        pool.close()
    finally:
        pool.join()
