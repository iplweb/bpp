"""Shared fixtures for pbn_komparator_zrodel tests."""

import pytest
from model_bakery import baker

from bpp.models import Dyscyplina_Naukowa
from pbn_api.models import Journal


@pytest.fixture
def pbn_journal_with_data():
    """Create a PBN Journal with points and disciplines data."""
    return Journal.objects.create(
        mongoId="test_journal_12345",
        status="ACTIVE",
        verificationLevel="VERIFIED",
        verified=True,
        versions=[
            {
                "current": True,
                "object": {
                    "title": "Test PBN Journal",
                    "points": {
                        "2022": {"points": 70},
                        "2023": {"points": 100},
                    },
                    # PBN uses dict format with code and name keys
                    # Codes "11" and "23" convert to "1.1" and "2.3"
                    "disciplines": [
                        {"code": "11", "name": "Matematyka"},
                        {"code": "23", "name": "Nauki chemiczne"},
                    ],
                },
            }
        ],
        title="Test PBN Journal",
    )


@pytest.fixture
def dyscyplina_1_01():
    """Create discipline 1.1 (normalized from PBN code 101)."""
    return baker.make(Dyscyplina_Naukowa, kod="1.1", nazwa="Matematyka")


@pytest.fixture
def dyscyplina_2_03():
    """Create discipline 2.3 (normalized from PBN code 203)."""
    return baker.make(Dyscyplina_Naukowa, kod="2.3", nazwa="Nauki chemiczne")
