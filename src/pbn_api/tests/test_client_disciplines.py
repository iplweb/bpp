"""
Tests for PBNClient discipline-related methods.

For upload tests, see test_client_upload.py
For sync tests, see test_client_sync.py
For helper/GUI tests, see test_client_helpers.py
"""

from pathlib import Path

import pytest
from django.db import connection
from pbn_client.const import PBN_GET_DISCIPLINES_URL

from bpp.decorators import json
from bpp.models import Dyscyplina_Naukowa
from pbn_api.models import TlumaczDyscyplin
from pbn_api.models.discipline import Discipline


def _load_disciplines_fixture(pbn_client):
    fixture_path = Path(__file__).parent / "fixture_test_get_disciplines.json"
    with open(fixture_path, "rb") as f:
        pbn_client.transport.return_values[PBN_GET_DISCIPLINES_URL] = json.loads(
            f.read()
        )


def test_get_disciplines(pbn_client):
    _load_disciplines_fixture(pbn_client)
    ret = pbn_client.get_disciplines()
    assert "validityDateFrom" in ret[0]


@pytest.mark.django_db
def test_download_disciplines(pbn_client):
    _load_disciplines_fixture(pbn_client)

    assert Discipline.objects.count() == 0
    pbn_client.download_disciplines()
    assert Discipline.objects.count() != 0


@pytest.mark.django_db
def test_sync_disciplines(pbn_client):
    _load_disciplines_fixture(pbn_client)

    d1 = Dyscyplina_Naukowa.objects.create(kod="5.1", nazwa="ekonomia i finanse")
    d2 = Dyscyplina_Naukowa.objects.create(kod="1.6", nazwa="nauka o kulturze")

    assert Dyscyplina_Naukowa.objects.count() == 2
    pbn_client.sync_disciplines()

    assert Dyscyplina_Naukowa.objects.count() > 2
    d1.refresh_from_db(), d2.refresh_from_db()

    assert TlumaczDyscyplin.objects.przetlumacz_dyscypline(d1, 2024) is not None

    assert TlumaczDyscyplin.objects.przetlumacz_dyscypline(d2, 2024) is not None


@pytest.mark.django_db(transaction=True)
def test_download_disciplines_fetches_outside_transaction(pbn_client):
    """D3/bugfix: remote-fetch (get_disciplines) NIE może dziać się w otwartej
    transakcji (wcześniej @transaction.atomic obejmował cały remote-call).

    ``transaction=True`` sprawia, że sam test nie owija się w atomic, więc
    ``connection.in_atomic_block`` w trakcie fetchu wiarygodnie odzwierciedla
    brak transakcji; upsert leci już wewnątrz transakcji sync_dictionary.
    """
    _load_disciplines_fixture(pbn_client)

    seen = {}
    original_get = pbn_client.get_disciplines

    def spying_get_disciplines():
        seen["fetch_in_atomic"] = connection.in_atomic_block
        return original_get()

    original_upsert = pbn_client._upsert_disciplines

    def spying_upsert(elems):
        seen["upsert_in_atomic"] = connection.in_atomic_block
        return original_upsert(elems)

    pbn_client.get_disciplines = spying_get_disciplines
    pbn_client._upsert_disciplines = spying_upsert

    pbn_client.download_disciplines()

    assert seen["fetch_in_atomic"] is False  # remote POZA transakcją
    assert seen["upsert_in_atomic"] is True  # zapis WEWNĄTRZ transakcji
