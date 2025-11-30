"""Publisher operations for PBN integrator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.db import transaction

from bpp.util import pbar
from pbn_api.models import Publisher
from pbn_integrator.utils.django_imports import _ensure_django_imports, matchuj_wydawce
from pbn_integrator.utils.threaded_page_getter import (
    ThreadedMongoDBSaver,
    threaded_page_getter,
)

if TYPE_CHECKING:
    from pbn_api.client import PBNClient


class PublisherGetter(ThreadedMongoDBSaver):
    """Threaded getter for publishers."""

    pbn_api_klass = Publisher


def pobierz_wydawcow_mnisw(client: PBNClient):
    """Fetch MNiSW publishers from PBN.

    Args:
        client: PBN client.
    """
    # XXX: TODO: obecnie jest ich 800, nie ma sensu robić threaded page getter tutaj...
    data = client.get_publishers_mnisw(page_size=1000)
    threaded_page_getter(
        client, data, klass=PublisherGetter, label="poboerz_wydawcow_mnisw"
    )


def pobierz_wydawcow_wszystkich(client: PBNClient):
    """Fetch all publishers from PBN.

    Args:
        client: PBN client.
    """
    data = client.get_publishers(page_size=1000)
    threaded_page_getter(
        client, data, klass=PublisherGetter, label="poboerz_wydawcow_wszystkich"
    )


@transaction.atomic
def integruj_wydawcow():
    """Integrate BPP publishers with PBN publishers."""
    _ensure_django_imports()

    # Najpierw dopasuj wydawcow z MNISWId
    for elem in pbar(
        Publisher.objects.filter(versions__contains=[{"current": True}]).filter(
            versions__0__object__has_key="mniswId"
        ),
        label="match wyd mnisw",
    ):
        w = matchuj_wydawce(elem.value("object", "publisherName"))
        if w is not None:
            if w.pbn_uid_id is None and w.pbn_uid_id != elem.pk:
                print(f"Przypisuje Wydawca PBN {elem} -> wydawca BPP {w}")
                w.pbn_uid_id = elem.pk
                w.save()

    # Dopasuj wszystkich
    for elem in pbar(
        Publisher.objects.filter(versions__contains=[{"current": True}]),
        label="match wyd wszyscy",
    ):
        w = matchuj_wydawce(elem.value("object", "publisherName"))
        if w is not None:
            if w.pbn_uid_id is None and w.pbn_uid_id != elem.pk:
                print(f"Przypisuje Wydawca PBN {elem} -> wydawca BPP {w}")
                w.pbn_uid_id = elem.pk
                w.save()
