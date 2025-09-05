# def pobierz_skasowane_prace(client: PBNClient):
#     pobierz_mongodb(
#         client.get_publications(status=DELETED, page_size=50),
#         Publication,
#         pbar_label="pobierz_skasowane_prace",
#     )


class ThreadedPageGetter:
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
            from pbn_api.integrator import zapisz_mongodb

            self.zapisz_mongodb = zapisz_mongodb
        self.zapisz_mongodb(elem, self.pbn_api_klass)


def threaded_page_getter(
    client,
    data,
    klass=ThreadedPageGetter,
    no_threads=12,
    label="getting...",
    method="threads",
):
    """Odświeża wszystkie publikacje, które są w lokalnej tabeli."""

    getter = klass()

    if method == "processes":
        import multiprocessing

        from pbn_api.integrator import (
            _bede_uzywal_bazy_danych_z_multiprocessing_z_django,
        )

        _bede_uzywal_bazy_danych_z_multiprocessing_z_django()

        pool = multiprocessing.get_context("fork").Pool(
            processes=no_threads, initializer=getter.pool_init, initargs=(client, data)
        )

    elif method == "threads":
        from multiprocessing.dummy import Pool

        pool = Pool(
            processes=no_threads, initializer=getter.pool_init, initargs=(client, data)
        )

    from bpp.util import pbar

    for _ in pbar(
        pool.imap_unordered(
            getter.get_single_page,
            range(0, data.total_pages),
        ),
        data.total_pages,
        label=label,
    ):
        pass

    pool.close()
    pool.join()
