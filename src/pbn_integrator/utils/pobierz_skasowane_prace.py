# def pobierz_skasowane_prace(client: PBNClient):
#     pobierz_mongodb(
#         client.get_publications(status=DELETED, page_size=50),
#         Publication,
#         pbar_label="pobierz_skasowane_prace",
#     )


def _init(_client, _data):
    import django

    django.setup()

    from django.db import connection

    connection.close()

    global client, pobierz_mongodb, Publication, zapisz_mongodb, data
    client = _client
    data = _data

    from pbn_api.integrator import pobierz_mongodb as _p

    pobierz_mongodb = _p

    from pbn_api.integrator import zapisz_mongodb as _p

    zapisz_mongodb = _p

    from pbn_api.models import Publication as _p

    Publication = _p


def _single_task(n):
    for elem in data.fetch_page(n):
        zapisz_mongodb(elem, Publication)


def pobierz_skasowane_prace(client):
    """Odświeża wszystkie publikacje, które są w lokalnej tabeli."""

    from multiprocessing import Pool

    from pbn_api.integrator import DELETED

    from bpp.util import pbar

    data = client.get_publications(status=DELETED, page_size=200)

    pool = Pool(processes=6, initializer=_init, initargs=(client, data))

    for _ in pbar(
        pool.imap_unordered(
            _single_task,
            range(0, data.total_pages),
        ),
        count=data.total_pages,
        label="pobierz_skasowane_prace",
    ):
        pass

    pool.close()
    pool.join()
