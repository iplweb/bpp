"""
Tests for PBNClient discipline-related methods.

For upload tests, see test_client_upload.py
For sync tests, see test_client_sync.py
For helper/GUI tests, see test_client_helpers.py
"""

from pathlib import Path

import pytest

from bpp.decorators import json
from bpp.models import Dyscyplina_Naukowa
from pbn_api.const import PBN_GET_DISCIPLINES_URL
from pbn_api.models import TlumaczDyscyplin
from pbn_api.models.discipline import Discipline


def test_get_disciplines(pbn_client):
    pbn_client.transport.return_values[PBN_GET_DISCIPLINES_URL] = json.loads(
        open(Path(__file__).parent / "fixture_test_get_disciplines.json", "rb").read()
    )
    ret = pbn_client.get_disciplines()
    assert "validityDateFrom" in ret[0]


@pytest.mark.django_db
def test_download_disciplines(pbn_client):
    pbn_client.transport.return_values[PBN_GET_DISCIPLINES_URL] = json.loads(
        open(Path(__file__).parent / "fixture_test_get_disciplines.json", "rb").read()
    )

    assert Discipline.objects.count() == 0
    pbn_client.download_disciplines()
    assert Discipline.objects.count() != 0


@pytest.mark.django_db
def test_sync_disciplines(pbn_client):
    pbn_client.transport.return_values[PBN_GET_DISCIPLINES_URL] = json.loads(
        open(Path(__file__).parent / "fixture_test_get_disciplines.json", "rb").read()
    )

    d1 = Dyscyplina_Naukowa.objects.create(kod="5.1", nazwa="ekonomia i finanse")
    d2 = Dyscyplina_Naukowa.objects.create(kod="1.6", nazwa="nauka o kulturze")

    assert Dyscyplina_Naukowa.objects.count() == 2
    pbn_client.sync_disciplines()

    assert Dyscyplina_Naukowa.objects.count() > 2
    d1.refresh_from_db(), d2.refresh_from_db()

    assert TlumaczDyscyplin.objects.przetlumacz_dyscypline(d1, 2024) is not None

    assert TlumaczDyscyplin.objects.przetlumacz_dyscypline(d2, 2024) is not None
