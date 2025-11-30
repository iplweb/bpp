"""Offline data operations for PBN integrator."""

from __future__ import annotations

import json
import os
from typing import TYPE_CHECKING

from django.db import transaction

from bpp.util import pbar
from pbn_api.const import ACTIVE, DELETED
from pbn_api.models import Publication, Scientist
from pbn_integrator.utils.mongodb_ops import pobierz_mongodb
from pbn_integrator.utils.multiprocessing_utils import (
    _bede_uzywal_bazy_danych_z_multiprocessing_z_django,
    initialize_pool,
)

if TYPE_CHECKING:
    from pbn_api.client import PBNClient


def pbn_file_path(db, current_page, status):
    """Generate file path for offline PBN data.

    Args:
        db: Database name (e.g., 'people', 'publications').
        current_page: Page number.
        status: Status (ACTIVE or DELETED).

    Returns:
        File path string.
    """
    return f"pbn_json_data/{db}_offline_{status}_{current_page}.json"


def _single_unit_offline(data, db, current_page, status):
    """Save a single page of data to offline file.

    Args:
        data: Page iterator.
        db: Database name.
        current_page: Page number.
        status: Status.
    """
    f = open(pbn_file_path(db, current_page, status), "w")
    f.write(json.dumps(data.fetch_page(current_page)))
    f.close()


def _pobierz_offline(fun, db):
    """Fetch data from PBN and save to offline files.

    Args:
        fun: Function to call to get data.
        db: Database name.
    """
    _bede_uzywal_bazy_danych_z_multiprocessing_z_django()

    p = initialize_pool()

    for status in [ACTIVE, DELETED]:
        data = fun(status=status, page_size=10000)

        params = [
            (data, db, current_page, status)
            for current_page in range(0, data.total_pages)
        ]

        for _ in pbar(
            p.istarmap(_single_unit_offline, params),
            label=f"pobierz_offline_{db}_{status}",
            count=len(params),
        ):
            pass

    p.close()
    p.join()


def pobierz_ludzi_offline(client: PBNClient):
    """Fetch people data from PBN to offline files.

    Args:
        client: PBN client.
    """
    return _pobierz_offline(client.get_people, "people")


def pobierz_prace_offline(client: PBNClient):
    """Fetch publications data from PBN to offline files.

    Args:
        client: PBN client.
    """
    return _pobierz_offline(client.get_publications, "publications")


def _single_unit_wgraj(current_page, status, db, model):
    """Load a single page of data from offline file to database.

    Args:
        current_page: Page number.
        status: Status.
        db: Database name.
        model: Django model class.
    """
    fn = pbn_file_path(db, current_page, status)
    if os.path.exists(fn):
        data = open(fn).read()
        if data:
            dane = json.loads(data)
            if dane:
                with transaction.atomic():
                    pobierz_mongodb(dane, model, disable_progress_bar=True)


def _wgraj_z_offline_do_bazy(db, model):
    """Load offline data to database.

    Args:
        db: Database name.
        model: Django model class.
    """
    _bede_uzywal_bazy_danych_z_multiprocessing_z_django()

    p = initialize_pool()

    for status in [ACTIVE, DELETED]:
        params = [(current_page, status, db, model) for current_page in range(1500)]

        for _ in pbar(
            p.istarmap(_single_unit_wgraj, params),
            label=f"wgraj_offline_{db}_{status}",
            count=len(params),
        ):
            pass

    p.close()
    p.join()


def wgraj_ludzi_z_offline_do_bazy():
    """Load people data from offline files to database."""
    return _wgraj_z_offline_do_bazy("people", Scientist)


def wgraj_prace_z_offline_do_bazy():
    """Load publications data from offline files to database."""
    return _wgraj_z_offline_do_bazy("publications", Publication)
