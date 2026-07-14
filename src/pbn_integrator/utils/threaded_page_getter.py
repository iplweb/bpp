"""BPP progress integration for reusable PBN page download services."""

from django_pbn_client.pages import (
    ThreadedModelSaver,
    ThreadedPageGetter,
    download_pages,
)

from bpp.util import pbar


class ThreadedMongoDBSaver(ThreadedModelSaver):
    """Compatibility saver using BPP's historical persistence entry point."""

    def process_element(self, elem):
        if not hasattr(self, "zapisz_mongodb"):
            from pbn_integrator.utils import zapisz_mongodb

            self.zapisz_mongodb = zapisz_mongodb
        self.zapisz_mongodb(elem, self.pbn_api_klass)


def threaded_page_getter(
    client,
    data,
    klass=ThreadedPageGetter,
    no_threads=12,
    label="getting...",
    method="threads",
    callback=None,
):
    """Download all paginator pages with BPP progress reporting."""
    if method == "processes":
        from pbn_integrator.utils import (
            _bede_uzywal_bazy_danych_z_multiprocessing_z_django,
        )

        _bede_uzywal_bazy_danych_z_multiprocessing_z_django()

    def progress(pages, total, progress_label):
        return pbar(
            pages,
            total,
            label=progress_label,
            callback=callback,
        )

    return download_pages(
        client,
        data,
        getter_class=klass,
        workers=no_threads,
        label=label,
        method=method,
        progress=progress,
    )


__all__ = [
    "ThreadedMongoDBSaver",
    "ThreadedPageGetter",
    "threaded_page_getter",
]
