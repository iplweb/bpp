# def pobierz_skasowane_prace(client: PBNClient):
#     pobierz_mongodb(
#         client.get_publications(status=DELETED, page_size=50),
#         Publication,
#         pbar_label="pobierz_skasowane_prace",
#     )


class ThreadedPageGetter:
    def __init__(self, max_workers=None, model_class=None):
        """Initialize ThreadedPageGetter with optional max_workers and model_class parameters

        Args:
            max_workers: Maximum number of worker threads (optional)
            model_class: Model class for subclasses like ThreadedMongoDBSaver (optional)
        """
        self.max_workers = max_workers
        self.model_class = model_class
        self.pbn_api_klass = model_class  # Alias for backward compatibility
        self.client = None
        self.data = None

    def pool_init(self, _client, _data):
        import django

        django.setup()

        self.client = _client
        self.data = _data

    def process_element(self, elem):
        raise NotImplementedError

    def get_single_page(self, n):
        for elem in self.data.fetch_page(n):
            self.process_element(elem)


class ThreadedMongoDBSaver(ThreadedPageGetter):
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
    """Odświeża wszystkie publikacje, które są w lokalnej tabeli."""

    # Create getter instance - pass no_threads as max_workers if supported
    try:
        getter = klass(max_workers=no_threads)
    except TypeError:
        # Fallback for klass that don't support max_workers
        getter = klass()

    # Use getter's max_workers if available, otherwise use no_threads parameter
    effective_threads = getattr(getter, "max_workers", None) or no_threads

    if method == "processes":
        import multiprocessing

        from pbn_integrator.utils import (
            _bede_uzywal_bazy_danych_z_multiprocessing_z_django,
        )

        _bede_uzywal_bazy_danych_z_multiprocessing_z_django()

        pool = multiprocessing.get_context("fork").Pool(
            processes=effective_threads,
            initializer=getter.pool_init,
            initargs=(client, data),
        )

    elif method == "threads":
        from multiprocessing.dummy import Pool

        pool = Pool(
            processes=effective_threads,
            initializer=getter.pool_init,
            initargs=(client, data),
        )

    from bpp.util import pbar

    for _ in pbar(
        pool.imap_unordered(
            getter.get_single_page,
            range(0, data.total_pages),
        ),
        data.total_pages,
        label=label,
        callback=callback,
    ):
        pass

    pool.close()
    pool.join()
