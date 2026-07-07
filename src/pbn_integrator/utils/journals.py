"""Journal/source operations for PBN integrator."""

from __future__ import annotations

import operator
from functools import reduce
from typing import TYPE_CHECKING

from django.db.models import F, Func, IntegerField, Q

from bpp.models import Zrodlo
from bpp.util import pbar
from pbn_api.const import ACTIVE, DELETED
from pbn_api.models import Journal
from pbn_integrator.utils.threaded_page_getter import (
    ThreadedMongoDBSaver,
    threaded_page_getter,
)

if TYPE_CHECKING:
    from pbn_api.client import PBNClient


class ZrodlaGetter(ThreadedMongoDBSaver):
    """Threaded getter for journals."""

    pbn_api_klass = Journal


def pobierz_zrodla(client: PBNClient):
    """Fetch journals from PBN.

    Args:
        client: PBN client.
    """
    for status in [DELETED, ACTIVE]:
        data = client.get_journals(status=status, page_size=500)
        threaded_page_getter(
            client,
            data,
            klass=ZrodlaGetter,
            label=f"poboerz_zrodla_{status}",
            no_threads=1,
        )


def pobierz_zrodla_mnisw(client: PBNClient, callback=None):
    """Fetch MNiSW journals from PBN.

    Args:
        client: PBN client.
        callback: Optional progress callback.
    """
    # status tu nie ma znaczenia
    data = client.get_journals_mnisw_v2(includeAllVersions="true", page_size=8)
    threaded_page_getter(
        client,
        data,
        klass=ZrodlaGetter,
        label="Pobieranie źródeł MNiSW",
        no_threads=24,
        callback=callback,
    )


def _zrodlo_query(zrodlo):
    """Build the combined ``Q`` lookup matching a ``Zrodlo`` to PBN journals."""
    queries = []

    if zrodlo.issn:
        queries.append(Q(issn=zrodlo.issn) | Q(eissn=zrodlo.issn))

    if zrodlo.e_issn:
        queries.append(Q(eissn=zrodlo.e_issn) | Q(issn=zrodlo.e_issn))

    queries.append(Q(title__iexact=zrodlo.nazwa))

    return reduce(operator.or_, queries)


def _najlepszy_journal(zrodlo, qry):
    """Return the best-matching PBN ``Journal`` for ``qry`` or ``None``.

    On multiple matches, prefer one carrying a ``mniswId``; otherwise pick
    the journal with the largest ``versions`` blob (longest description).
    """
    try:
        return Journal.objects.get(qry)
    except Journal.DoesNotExist:
        return None
    except Journal.MultipleObjectsReturned:
        # warnings.warn(
        #     f"Znaleziono liczne dopasowania w PBN dla {zrodlo}, szukam czy jakies ma mniswId"
        # )
        for u in Journal.objects.filter(qry):
            if u.mniswId is not None:
                return u

        print(
            f"Znaleziono liczne dopasowania w PBN dla {zrodlo}, żadnie nie ma mniswId, wybieram to z "
            f"najdłuższym opisem"
        )
        return (
            Journal.objects.filter(qry)
            .annotate(
                json_len=Func(
                    F("versions"),
                    function="pg_column_size",
                    output_field=IntegerField(),
                )
            )
            .order_by("-json_len")
            .first()
        )


def integruj_zrodla(disable_progress_bar=False):
    """Integrate BPP sources with PBN journals.

    Args:
        disable_progress_bar: Whether to disable progress bar.
    """
    for zrodlo in pbar(
        Zrodlo.objects.filter(pbn_uid_id=None),
        label="Integracja zrodel",
        disable_progress_bar=disable_progress_bar,
    ):
        u = _najlepszy_journal(zrodlo, _zrodlo_query(zrodlo))

        if u is not None:
            zrodlo.pbn_uid = u
            zrodlo.save()
            print(f"\nZNALEZIONO dopasowania w PBN dla {zrodlo} -> {zrodlo.pbn_uid}")
            continue

        print(f"\nNie znaleziono dopasowania w PBN dla {zrodlo}")
