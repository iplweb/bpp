from pbn_api.exceptions import BrakIDPracyPoStroniePBN
from pbn_api.integrator import DELETED


def odswiez_tabele_publikacji_init(_client):
    import django

    django.setup()

    global client, _pobierz_pojedyncza_prace
    client = _client

    from pbn_api.integrator import _pobierz_pojedyncza_prace as f

    _pobierz_pojedyncza_prace = f


def odswiez_tabele_single_task(mongoId):
    from pbn_api.models import Publication

    from bpp.models import Rekord

    try:
        _pobierz_pojedyncza_prace(client, mongoId)
    except BrakIDPracyPoStroniePBN:
        try:
            rekord_bpp = Rekord.objects.get(pbn_uid_id=mongoId)
        except Rekord.DoesNotExist:
            rekord_bpp = None

        print(
            f"Brak pracy po stronie PBN z id {mongoId}"
            f", usuwam z PBN, po stronie BPP rekord byl: {rekord_bpp}"
        )
        Publication.objects.get(pk=mongoId).delete()


def odswiez_tabele_publikacji(client):
    """Odświeża wszystkie publikacje, które są w lokalnej tabeli."""
    from pbn_api.integrator import _bede_uzywal_bazy_danych_z_multiprocessing_z_django
    from pbn_api.models import Publication

    from bpp.util import pbar

    _bede_uzywal_bazy_danych_z_multiprocessing_z_django()

    from multiprocessing import Pool

    pool = Pool(
        processes=8, initializer=odswiez_tabele_publikacji_init, initargs=(client,)
    )

    ids = list(Publication.objects.exclude(status=DELETED).values_list("pk", flat=True))
    for _ in pbar(
        pool.imap_unordered(
            odswiez_tabele_single_task,
            ids,
        ),
        count=len(ids),
        label="odswiez_tabele_publikacji",
    ):
        pass

    pool.close()
    pool.join()
