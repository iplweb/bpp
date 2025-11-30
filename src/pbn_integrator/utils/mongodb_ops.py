"""MongoDB save operations for PBN integrator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

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


@transaction.atomic
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
    defaults = dict(
        status=elem["status"],
        verificationLevel=elem["verificationLevel"],
        verified=elem["verified"],
        versions=elem["versions"],
        **extra,
    )

    existing = klass.objects.select_for_update().filter(pk=elem["mongoId"])

    created = False
    try:
        v = existing.get()
    except klass.DoesNotExist:
        v = klass.objects.create(pk=elem["mongoId"], **defaults)
        created = True

    if not created:
        needs_saving = False

        for key in extra:
            if getattr(v, key) != extra.get(key):
                setattr(v, key, extra.get(key))
                needs_saving = True

        if elem["versions"] != v.versions:
            v.versions = elem["versions"]
            needs_saving = True

        if needs_saving:
            v.save()

    return v


def ensure_publication_exists(client, publicationId):
    """Ensure a publication exists in the database, fetching from PBN if necessary.

    Args:
        client: PBN client.
        publicationId: The publication ID.
    """
    try:
        publicationId = Publication.objects.get(pk=publicationId)
    except Publication.DoesNotExist:
        zapisz_mongodb(
            client.get_publication_by_id(publicationId), Publication, client=client
        )


def ensure_person_exists(client: PBNClient, personId):
    """Ensure a person/scientist exists in the database, fetching from PBN if necessary.

    Args:
        client: PBN client.
        personId: The person ID.
    """
    try:
        personId = Scientist.objects.get(pk=personId)
    except Scientist.DoesNotExist:
        zapisz_mongodb(client.get_person_by_id(personId), Scientist, client=client)


def ensure_institution_exists(client: PBNClient, institutionId):
    """Ensure an institution exists in the database, fetching from PBN if necessary.

    Args:
        client: PBN client.
        institutionId: The institution ID.
    """
    try:
        institutionId = Institution.objects.get(pk=institutionId)
    except Institution.DoesNotExist:
        zapisz_mongodb(
            client.get_publication_by_id(institutionId), Institution, client=client
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
            print(
                f"Podczas zapisywania publikacji instytucji, dla {elem['publicationId']} serwer "
                f"PBN zwrócił bład 500. Publikacja instytucji może zostac nie zapisana poprawnie. Dump danych "
                f"publikacji: {elem}"
            )
            return

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
            print(
                f"Podczas próby pobrania danych o nie-istniejącej obecnie po naszej stronie publikacji o id"
                f" {elem['publicationId']} z PBNu, wystąpił błąd wewnętrzny serwera po ich stronie. Dane "
                f"dotyczące oświadczeń z tej publikacji nie zostały zapisane. "
            )
            return

    try:
        ensure_institution_exists(client, elem["institutionId"])
    except HttpException as e:
        if e.status_code == 500:
            print(
                f"Podczas próby pobrania danych o nie-istniejącej obecnie po naszej stronie publikacji o id"
                f" {elem['publicationId']} z PBNu, wystąpił błąd wewnętrzny serwera po ich stronie. Dane "
                f"dotyczące oświadczeń z tej publikacji nie zostały zapisane. "
            )
            return

    try:
        ensure_person_exists(client, elem["personId"])
    except HttpException as e:
        if e.status_code == 500:
            print(
                f"Podczas próby pobrania danych o nie-istniejącej obecnie po naszej stronie publikacji o id"
                f" {elem['publicationId']} z PBNu, wystąpił błąd wewnętrzny serwera po ich stronie. Dane "
                f"dotyczące oświadczeń z tej publikacji nie zostały zapisane. "
            )
            return

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
    """
    if fun is None:
        fun = zapisz_mongodb

    # Determine the total count
    count = None
    if hasattr(elems, "total_elements"):
        count = elems.total_elements
    elif hasattr(elems, "__len__"):
        count = len(elems)
    else:
        # Try to get count from iterator if possible
        try:
            count = elems.count() if hasattr(elems, "count") else elems.count
        except Exception:
            count = None

    # Use pbar with callback support for database progress tracking
    for elem in pbar(
        elems,
        count,
        pbar_label,
        disable_progress_bar=disable_progress_bar,
        callback=callback,
    ):
        fun(elem, klass, client=client)
