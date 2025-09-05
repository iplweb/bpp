from pbn_api.integrator import DELETED
from pbn_api.integrator.threaded_page_getter import (
    ThreadedMongoDBSaver,
    threaded_page_getter,
)
from pbn_api.models import Publication


class DeletedPublicationGetter(ThreadedMongoDBSaver):
    pbn_api_klass = Publication


def pobierz_skasowane_prace(client):
    """Odświeża wszystkie publikacje skasowane."""
    data = client.get_publications(status=DELETED, page_size=200)
    threaded_page_getter(
        client,
        data,
        klass=DeletedPublicationGetter,
        label="pobierz_skasowane_prace",
        no_threads=6,
    )
