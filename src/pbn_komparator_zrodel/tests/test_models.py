"""Tests for models in pbn_komparator_zrodel."""

from decimal import Decimal

import pytest
from model_bakery import baker

from bpp.models import Zrodlo

from ..models import KomparatorZrodelMeta, RozbieznoscZrodlaPBN


@pytest.mark.django_db
def test_rozbieznosc_zrodla_pbn_model_creation(pbn_journal_with_data):
    """Test creating RozbieznoscZrodlaPBN model."""
    zrodlo = baker.make(Zrodlo, nazwa="Test Journal", pbn_uid=pbn_journal_with_data)

    rozbieznosc = RozbieznoscZrodlaPBN.objects.create(
        zrodlo=zrodlo,
        rok=2023,
        ma_rozbieznosc_punktow=True,
        punkty_bpp=Decimal("50.00"),
        punkty_pbn=Decimal("100.00"),
        ma_rozbieznosc_dyscyplin=False,
    )

    assert rozbieznosc.ma_jakiekolwiek_rozbieznosci is True
    assert str(rozbieznosc) == "Rozbieżność: Test Journal (2023)"


@pytest.mark.django_db
def test_komparator_zrodel_meta_singleton():
    """Test KomparatorZrodelMeta singleton behavior."""
    meta1 = KomparatorZrodelMeta.get_instance()
    meta2 = KomparatorZrodelMeta.get_instance()

    assert meta1.pk == meta2.pk == 1
