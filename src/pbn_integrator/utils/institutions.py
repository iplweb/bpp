"""Institution operations for PBN integrator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from bpp.models import Jednostka, Uczelnia
from pbn_api.const import ACTIVE, DELETED
from pbn_api.models import Institution
from pbn_integrator.utils.mongodb_ops import pobierz_mongodb, zapisz_mongodb
from pbn_integrator.utils.threaded_page_getter import (
    ThreadedMongoDBSaver,
    threaded_page_getter,
)

if TYPE_CHECKING:
    from pbn_api.client import PBNClient


class InstitutionGetter(ThreadedMongoDBSaver):
    """Threaded getter for institutions."""

    pbn_api_klass = Institution


def pobierz_instytucje(client: PBNClient, callback=None):
    """Fetch institutions from PBN.

    Args:
        client: PBN client.
        callback: Optional progress callback.
    """
    for status in [ACTIVE, DELETED]:
        pobierz_mongodb(
            client.get_institutions(status=status, page_size=1000),
            Institution,
            pbar_label=f"Pobieranie instytucji ({status})",
            callback=callback,
        )


def pobierz_instytucje_polon(client: PBNClient, callback=None):
    """Fetch POLON institutions from PBN.

    Args:
        client: PBN client.
        callback: Optional progress callback.
    """
    data = client.get_institutions_polon(page_size=10)

    threaded_page_getter(
        client,
        data,
        klass=InstitutionGetter,
        label="Pobieranie instytucji POLON",
        no_threads=24,
        callback=callback,
    )


def integruj_uczelnie():
    """Integrate the default university with PBN."""
    uczelnia = Uczelnia.objects.get_default()

    if uczelnia.pbn_uid_id is not None:
        return

    try:
        u = Institution.objects.get(
            versions__contains=[{"current": True, "object": {"name": uczelnia.nazwa}}]
        )
    except Institution.DoesNotExist as e:
        raise Exception(
            f"Nie umiem dopasowac uczelni po nazwie: {uczelnia.nazwa}"
        ) from e

    if uczelnia.pbn_uid_id != u.mongoId:
        uczelnia.pbn_uid = u
        uczelnia.save()


def integruj_instytucje():
    """Integrate university units with PBN institutions."""
    uczelnia = Uczelnia.objects.get_default()
    assert uczelnia.pbn_uid_id

    for j in Jednostka.objects.filter(skupia_pracownikow=True):
        try:
            u = Institution.objects.get(
                versions__contains=[
                    {
                        "current": True,
                        "object": {"name": j.nazwa, "parentId": uczelnia.pbn_uid_id},
                    }
                ]
            )
        except Institution.MultipleObjectsReturned:
            print(f"x*X Liczne dopasowania dla jednostki: {j}")
            continue

        except Institution.DoesNotExist:
            print(f"XXX Brak dopasowania dla jednostki: {j}")
            continue

        if j.pbn_uid_id != u.mongoId:
            j.pbn_uid_id = u.mongoId
            j.save()


def pobierz_instytucje_po_id(client: PBNClient, institution_id):
    """Fetch a single institution by ID.

    Args:
        client: PBN client.
        institution_id: Institution ID.

    Returns:
        The Institution object.
    """
    return zapisz_mongodb(
        client.get_institution_by_id(institution_id), Institution, client
    )
