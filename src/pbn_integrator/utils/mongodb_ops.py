"""MongoDB save operations for PBN integrator."""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING

import rollbar
from django_pbn_client.download import download_to_model
from django_pbn_client.persistence import (
    download_pbn_objects,
    get_or_download,
    upsert_pbn_object,
)

from bpp.util import pbar
from pbn_api.exceptions import HttpException
from pbn_api.models import (
    Institution,
    OswiadczenieInstytucji,
    Publication,
    PublikacjaInstytucji,
    Scientist,
)

if TYPE_CHECKING:
    from pbn_api.client import PBNClient

logger = logging.getLogger(__name__)


def zapisz_mongodb(elem, klass, client=None, **extra):
    """Save a MongoDB element to the database.

    Args:
        elem: The element data from PBN API.
        klass: The Django model class.
        client: Optional PBN client.
        **extra: Extra fields to save.

    Returns:
        The created or updated model instance.
    """
    return upsert_pbn_object(elem, klass, client=client, **extra)


def ensure_publication_exists(client, publicationId):
    """Ensure a publication exists in the database, fetching from PBN if necessary.

    Args:
        client: PBN client.
        publicationId: The publication ID.
    """
    get_or_download(
        Publication,
        publicationId,
        fetch=client.get_publication_by_id,
        save=zapisz_mongodb,
        client=client,
    )


def ensure_person_exists(client: PBNClient, personId):
    """Ensure a person/scientist exists in the database, fetching from PBN if necessary.

    Args:
        client: PBN client.
        personId: The person ID.
    """
    get_or_download(
        Scientist,
        personId,
        fetch=client.get_person_by_id,
        save=zapisz_mongodb,
        client=client,
    )


def ensure_institution_exists(client: PBNClient, institutionId):
    """Ensure an institution exists in the database, fetching from PBN if necessary.

    Args:
        client: PBN client.
        institutionId: The institution ID.
    """
    get_or_download(
        Institution,
        institutionId,
        fetch=client.get_institution_by_id,
        save=zapisz_mongodb,
        client=client,
    )


def zapisz_publikacje_instytucji(elem, klass, client=None, **extra):
    """Save institution publication data.

    Args:
        elem: The publication data.
        klass: Not used, kept for compatibility.
        client: PBN client.
        **extra: Extra arguments (not used).
    """
    try:
        ensure_publication_exists(client, elem["publicationId"])
    except HttpException as e:
        if e.status_code == 500:
            logger.warning(
                "PBN zwrócił błąd 500 podczas pobierania publikacji %s. "
                "Publikacja instytucji może nie zostać zapisana poprawnie. "
                "Dane: %s",
                elem["publicationId"],
                elem,
            )
            rollbar.report_exc_info(
                sys.exc_info(),
                extra_data={
                    "publicationId": elem["publicationId"],
                    "elem": elem,
                },
            )
            return
        else:
            raise

    try:
        ensure_institution_exists(client, elem["institutionId"])
    except HttpException as e:
        if e.status_code == 500:
            logger.warning(
                "PBN zwrócił błąd 500 podczas pobierania instytucji %s. "
                "Publikacja instytucji może nie zostać zapisana poprawnie. "
                "Dane: %s",
                elem["institutionId"],
                elem,
            )
            rollbar.report_exc_info(
                sys.exc_info(),
                extra_data={
                    "institutionId": elem["institutionId"],
                    "elem": elem,
                },
            )
            return
        else:
            raise

    try:
        ensure_person_exists(client, elem["insPersonId"])
    except HttpException as e:
        if e.status_code == 500:
            logger.warning(
                "PBN zwrócił błąd 500 podczas pobierania osoby %s. "
                "Publikacja instytucji może nie zostać zapisana poprawnie. "
                "Dane: %s",
                elem["insPersonId"],
                elem,
            )
            rollbar.report_exc_info(
                sys.exc_info(),
                extra_data={
                    "insPersonId": elem["insPersonId"],
                    "elem": elem,
                },
            )
            return
        else:
            raise

    rec, _ign = PublikacjaInstytucji.objects.get_or_create(
        institutionId_id=elem["institutionId"],
        publicationId_id=elem["publicationId"],
        insPersonId_id=elem["insPersonId"],
    )

    changed = False
    for key in (
        "publicationVersion",
        "publicationYear",
        "publicationType",
        "userType",
        "snapshot",
    ):
        current = getattr(rec, key)
        server = elem.get(key)
        if current != server:
            setattr(rec, key, server)
            changed = True
    if changed:
        rec.save()


def zapisz_oswiadczenie_instytucji(elem, klass, client=None, **extra):
    """Save institution statement data.

    Args:
        elem: The statement data.
        klass: Not used, kept for compatibility.
        client: PBN client.
        **extra: Extra arguments (not used).
    """
    # {'id': '121339', 'institutionId': '5e70918b878c28a04737de51',
    # 'personId': '5e709330878c28a0473a4a0e', 'publicationId': '5ebff589ad49b31ccec25471',
    # 'addedTimestamp': '2020.05.16', 'area': '304', 'inOrcid': False, 'type': 'AUTHOR'}
    for var in "addedTimestamp", "statedTimestamp":
        if elem.get(var):
            elem[var] = elem[var].replace(".", "-")

    try:
        ensure_publication_exists(client, elem["publicationId"])
    except HttpException as e:
        if e.status_code == 500:
            logger.warning(
                "PBN zwrócił błąd 500 podczas pobierania publikacji %s "
                "dla oświadczenia instytucji. Dane: %s",
                elem["publicationId"],
                elem,
            )
            rollbar.report_exc_info(
                sys.exc_info(),
                extra_data={
                    "publicationId": elem["publicationId"],
                    "elem": elem,
                },
            )
            return
        else:
            raise

    try:
        ensure_institution_exists(client, elem["institutionId"])
    except HttpException as e:
        if e.status_code == 500:
            logger.warning(
                "PBN zwrócił błąd 500 podczas pobierania instytucji %s "
                "dla oświadczenia instytucji. Dane: %s",
                elem["institutionId"],
                elem,
            )
            rollbar.report_exc_info(
                sys.exc_info(),
                extra_data={
                    "institutionId": elem["institutionId"],
                    "elem": elem,
                },
            )
            return
        else:
            raise

    try:
        ensure_person_exists(client, elem["personId"])
    except HttpException as e:
        if e.status_code == 500:
            logger.warning(
                "PBN zwrócił błąd 500 podczas pobierania osoby %s "
                "dla oświadczenia instytucji. Dane: %s",
                elem["personId"],
                elem,
            )
            rollbar.report_exc_info(
                sys.exc_info(),
                extra_data={
                    "personId": elem["personId"],
                    "elem": elem,
                },
            )
            return
        else:
            raise

    for key in "institution", "person", "publication":
        elem[f"{key}Id_id"] = elem[f"{key}Id"]
        del elem[f"{key}Id"]

    OswiadczenieInstytucji.objects.update_or_create(id=elem["id"], defaults=elem)


def pobierz_mongodb(
    elems,
    klass,
    pbar_label="pobierz_mongodb",
    fun=None,
    client=None,
    disable_progress_bar=False,
    callback=None,
    on_error="raise",
):
    """Fetch and save elements from PBN API.

    Args:
        elems: Iterator of elements from PBN API.
        klass: Django model class.
        pbar_label: Label for progress bar.
        fun: Function to use for saving (defaults to zapisz_mongodb).
        client: PBN client.
        disable_progress_bar: Whether to disable progress bar.
        callback: Optional callback for progress tracking.
        on_error: Zachowanie przy błędzie zapisu POJEDYNCZEGO rekordu do
            lokalnego lustra BPP (``IntegrityError``, zły kształt danych itp.):

            - ``"raise"`` (default) — fail-fast: pierwszy błąd propaguje i
              przerywa cały batch (zachowanie historyczne). Zwraca ``None``.
            - ``"skip"`` — skip-and-log-and-continue: zły rekord jest logowany
              (pełny traceback) i liczony, import reszty listy kończy się.
              Deleguje do pakietowego ``download_to_model`` i zwraca
              ``DownloadResult(processed, errored)``. Przydatne przy masowych
              synchronizacjach (tysiące rekordów), gdzie jeden zepsuty rekord
              nie powinien wywalać całego przebiegu.
    """
    if fun is None:
        fun = zapisz_mongodb

    def progress(elements, total, _label):
        # Używamy ``pbar_label`` (nie ``_label`` z delegata) — ``download_to_model``
        # nie forwarduje etykiety, więc trzymamy ją stałą w obu trybach.
        return pbar(
            elements,
            total,
            pbar_label,
            disable_progress_bar=disable_progress_bar,
            callback=callback,
        )

    if on_error == "raise":
        return download_pbn_objects(
            elems,
            klass,
            label=pbar_label,
            save=fun,
            client=client,
            progress=progress,
        )
    if on_error == "skip":
        # ``elems`` jest już zbudowanym paginatorem/iteratorem — fasada oczekuje
        # fabryki (zero-arg), więc oddajemy gotowy zasób. Domyślne
        # ``concurrency=None`` → ścieżka sekwencyjna (bez ponownego requestu).
        return download_to_model(
            lambda: elems,
            klass,
            save=fun,
            client=client,
            progress=progress,
        )
    raise ValueError(f"on_error musi być 'raise' albo 'skip', otrzymano {on_error!r}")
