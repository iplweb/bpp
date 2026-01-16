"""Publication operations for PBN integrator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from tqdm import tqdm

from bpp.const import PBN_MIN_ROK
from bpp.models import Rekord
from bpp.util import pbar
from pbn_api.const import ACTIVE
from pbn_api.exceptions import BrakIDPracyPoStroniePBN, HttpException
from pbn_api.models import Publication, PublikacjaInstytucji_V2
from pbn_integrator.utils.mongodb_ops import (
    pobierz_mongodb,
    zapisz_mongodb,
    zapisz_oswiadczenie_instytucji,
    zapisz_publikacje_instytucji,
)
from pbn_integrator.utils.multiprocessing_utils import (
    _bede_uzywal_bazy_danych_z_multiprocessing_z_django,
    initialize_pool,
    wait_for_results,
)
from pbn_integrator.utils.threaded_page_getter import (
    ThreadedPageGetter,
    threaded_page_getter,
)

if TYPE_CHECKING:
    from pbn_api.client import PBNClient


class PublikacjeInstytucjiGetter(ThreadedPageGetter):
    """Threaded getter for institution publications."""

    def process_element(self, elem):
        zapisz_publikacje_instytucji(elem, None, client=self.client)


class OswiadczeniaInstytucjiGetter(ThreadedPageGetter):
    """Threaded getter for institution statements."""

    def process_element(self, elem):
        zapisz_oswiadczenie_instytucji(elem, None, client=self.client)


class PublikacjeInstytucjiV2Getter(ThreadedPageGetter):
    """Threaded getter for institution publications v2."""

    def process_element(self, elem):
        zapisz_publikacje_instytucji_v2(self.client, elem)


def pobierz_prace(client: PBNClient):
    """Fetch active publications from PBN.

    Args:
        client: PBN client.
    """
    pobierz_mongodb(
        client.get_publications(status=ACTIVE, page_size=5000),
        Publication,
        pbar_label="pobierz_aktywne_prace",
    )


def pobierz_publikacje_z_instytucji(
    client: PBNClient, callback=None, use_threads=True, no_threads=24
):
    """Fetch institution publications from PBN.

    Args:
        client: PBN API client.
        callback: Optional progress callback for database tracking.
        use_threads: Whether to use threading (default: True).
        no_threads: Number of threads to use (default: 8).
    """
    if use_threads:
        # Use threaded version for better performance
        data = client.get_institution_publications(page_size=10)

        threaded_page_getter(
            client,
            data,
            klass=PublikacjeInstytucjiGetter,
            label="Pobieranie publikacji instytucji",
            no_threads=no_threads,
            callback=callback,
        )
    else:
        # Fall back to single-threaded version if needed
        pobierz_mongodb(
            client.get_institution_publications(page_size=2000),
            None,
            fun=zapisz_publikacje_instytucji,
            client=client,
            pbar_label="Pobieranie publikacji instytucji",
            callback=callback,
        )


def zapisz_publikacje_instytucji_v2(client: PBNClient, elem: dict):
    """Save institution publication v2 data.

    Args:
        client: PBN client.
        elem: Publication data dict.

    Returns:
        Tuple of (PublikacjaInstytucji_V2, created).
    """
    uuid = elem.get("uuid")
    objectId_id = elem.get("objectId")

    try:
        objectId = Publication.objects.get(pk=objectId_id)
    except Publication.DoesNotExist:
        objectId = _pobierz_pojedyncza_prace(client, objectId_id)
        print(f"Pobrano brakującą pracę: {objectId}")

    return PublikacjaInstytucji_V2.objects.update_or_create(
        uuid=uuid, objectId=objectId, defaults={"json_data": elem}
    )


def pobierz_publikacje_z_instytucji_v2(
    client: PBNClient, callback=None, use_threads=True, no_threads=8
):
    """Fetch institution publications v2 from PBN.

    Args:
        client: PBN API client.
        callback: Optional progress callback for database tracking.
        use_threads: Whether to use threading (default: True).
        no_threads: Number of threads to use (default: 8).
    """
    if use_threads:
        # Use threaded version for better performance
        data = client.get_institution_publications_v2()

        threaded_page_getter(
            client,
            data,
            klass=PublikacjeInstytucjiV2Getter,
            label="Pobieranie publikacji instytucji v2",
            no_threads=no_threads,
            callback=callback,
        )
    else:
        # Fall back to single-threaded version if needed
        res = client.get_institution_publications_v2()
        for elem in tqdm(res, total=res.count()):
            zapisz_publikacje_instytucji_v2(client, elem)


def pobierz_oswiadczenia_z_instytucji(
    client: PBNClient, callback=None, use_threads=True, no_threads=8
):
    """Fetch institution statements from PBN.

    Args:
        client: PBN API client.
        callback: Optional progress callback for database tracking.
        use_threads: Whether to use threading (default: True).
        no_threads: Number of threads to use (default: 8).
    """
    if use_threads:
        # Use threaded version for better performance
        data = client.get_institution_statements(page_size=1000)

        threaded_page_getter(
            client,
            data,
            klass=OswiadczeniaInstytucjiGetter,
            label="Pobieranie oświadczeń instytucji",
            no_threads=no_threads,
            callback=callback,
        )
    else:
        # Fall back to single-threaded version if needed
        pobierz_mongodb(
            client.get_institution_statements(page_size=1000),
            None,
            fun=zapisz_oswiadczenie_instytucji,
            client=client,
            pbar_label="Pobieranie oświadczeń instytucji",
            callback=callback,
        )


def _pobierz_prace_po_elemencie(
    client: PBNClient, element, nd, matchuj=True, value_from_rec=None, **kw
):
    """Fetch publications by a specific element (DOI, ISBN, etc.).

    Args:
        client: PBN client.
        element: Element type ('doi', 'isbn', etc.).
        nd: Normalized value.
        matchuj: Whether to match to BPP records.
        value_from_rec: Original record value.
        **kw: Additional keyword arguments.

    Returns:
        List of matched BPP records.
    """
    ret = []
    base_kw = {element: nd}
    base_kw.update(kw)

    for elem in client.search_publications(**base_kw):
        publication = zapisz_mongodb(
            client.get_publication_by_id(elem["mongoId"]), Publication
        )

        p = publication.matchuj_do_rekordu_bpp()
        if p is None:
            print(
                f"XXX mimo pobrania pracy po {element.upper()} {nd}, zwrotnie NIE pasuje ona do pracy w BPP "
                f"-- rok {publication.year} lub tytul {publication.title} nie daja sie dopasowac. Blad w "
                f"zapisie {element.upper()}? Niepoprawne {element.upper()}? Oryginalny obiekt: {value_from_rec}"
            )
            continue

        p = p.original

        if p in ret:
            continue

        if p.pbn_uid_id == publication.mongoId:
            # Juz zmatchowany
            continue

        # Co w sytuacji p.pbn_uid_id != publication.mongoId? Rekord zmatchowany z innym, teraz pasuje do innego?
        # Nic. Na ten moment nadpisujemy to po cichu (2.09.2021), jest to moja swiadoma decyzja (mpasternak)
        # poniewaz z tysiaca komunikatow o tej sytuacji nic nie wynikalo a zazwyczaj wychodzilo na to, ze rekordy
        # byly niepoprawnie zmatchowane.

        p.pbn_uid_id = publication.mongoId
        p.save(update_fields=["pbn_uid_id"])
        ret.append(p)

    return ret


def pobierz_prace_po_doi(client: PBNClient):
    """Fetch publications by DOI.

    Args:
        client: PBN client.
    """
    from pbn_integrator.utils.django_imports import normalize_doi

    dois = set()
    for praca in pbar(
        Rekord.objects.all()
        .exclude(doi=None)
        .exclude(doi="")
        .filter(pbn_uid_id=None)
        .filter(rok__gte=PBN_MIN_ROK),
        label="pobierz_prace_po_doi",
    ):
        nd = normalize_doi(praca.doi)
        dois.add(nd)

    _bede_uzywal_bazy_danych_z_multiprocessing_z_django()

    p = initialize_pool()

    results = []

    for doi in dois:
        results.append(
            p.apply_async(
                _pobierz_prace_po_elemencie,
                args=(
                    client,
                    "doi",
                    doi,
                ),
            )
        )

    wait_for_results(p, results)


def pobierz_prace_po_isbn(client: PBNClient):
    """Fetch publications by ISBN.

    Args:
        client: PBN client.
    """
    from pbn_integrator.utils.django_imports import normalize_isbn

    isbns = set()
    for praca in pbar(
        Rekord.objects.all()
        .exclude(isbn=None)
        .exclude(isbn="")
        .filter(pbn_uid_id=None)
        .filter(rok__gte=PBN_MIN_ROK)
        .filter(wydawnictwo_nadrzedne_id=None),
        label="pobierz_prace_po_isbn",
    ):
        nd = normalize_isbn(praca.isbn)
        isbns.add(nd)

    _bede_uzywal_bazy_danych_z_multiprocessing_z_django()

    p = initialize_pool()

    results = []

    for isbn in isbns:
        results.append(
            p.apply_async(
                _pobierz_prace_po_elemencie,
                args=(
                    client,
                    "isbn",
                    isbn,
                ),
            )
        )

    wait_for_results(p, results)


def _pobierz_pojedyncza_prace(client, publicationId):
    """Fetch a single publication by ID.

    Args:
        client: PBN client.
        publicationId: Publication ID.

    Returns:
        The Publication object or None.
    """
    try:
        data = client.get_publication_by_id(publicationId)
    except HttpException as e:
        if (
            e.status_code == 422
            and f"Publication with ID {publicationId} was not exists!" in e.content
            # "was not exists" to oryginalna pisownia błędu z PBNu.
        ):
            raise BrakIDPracyPoStroniePBN(e) from e

        if e.status_code == 500 and "Internal server error" in e.content:
            print(
                f"\r\nSerwer PBN zwrocil blad 500 dla PBN UID {publicationId} --> {e.content}"
            )
            return
        raise e
    return zapisz_mongodb(data, Publication, client)


def pobierz_rekordy_publikacji_instytucji(client: PBNClient):
    """Fetch publication records for institution.

    Args:
        client: PBN client.
    """
    seen = set()
    for elem in pbar(
        client.get_institution_publications(page_size=1000),
        label="scan pobierz_rekordy_publikacji_instytucji",
    ):
        publicationId = elem["publicationId"]
        seen.add(publicationId)

    _bede_uzywal_bazy_danych_z_multiprocessing_z_django()
    pool = initialize_pool(multipler=2)

    args = [(client, _id) for _id in seen]
    for _ in pbar(
        pool.istarmap(_pobierz_pojedyncza_prace, args),
        label="pobierz_rekordy_publikacj_instytucji",
        count=len(args),
    ):
        pass

    pool.close()
    pool.join()
