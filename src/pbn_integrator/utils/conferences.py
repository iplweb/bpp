"""Conference operations for PBN integrator."""

from __future__ import annotations

from typing import TYPE_CHECKING

from pbn_api.models import Conference
from pbn_integrator.utils.mongodb_ops import pobierz_mongodb

if TYPE_CHECKING:
    from pbn_api.client import PBNClient


def pobierz_konferencje(client: PBNClient, callback=None):
    """Fetch conferences from PBN.

    Args:
        client: PBN client.
        callback: Optional progress callback.
    """
    pobierz_mongodb(
        client.get_conferences_mnisw(page_size=1000),
        Conference,
        pbar_label="Pobieranie konferencji",
        callback=callback,
    )
