"""Tests for KomparatorZrodelPBN core comparison logic."""

from decimal import Decimal

import pytest
from model_bakery import baker

from bpp.models import Punktacja_Zrodla, Zrodlo

from ..models import RozbieznoscZrodlaPBN
from ..utils import KomparatorZrodelPBN


@pytest.mark.django_db(transaction=True)
def test_komparator_finds_points_discrepancy(
    pbn_journal_with_data, dyscyplina_1_01, dyscyplina_2_03
):
    """Test that komparator finds discrepancy when BPP points differ from PBN."""
    zrodlo = baker.make(Zrodlo, nazwa="Test Journal", pbn_uid=pbn_journal_with_data)

    # Create BPP punktacja with different value than PBN (70 vs 100 for 2023)
    Punktacja_Zrodla.objects.create(
        zrodlo=zrodlo, rok=2023, punkty_kbn=Decimal("50.00")
    )

    # Also add correct discipline assignment to avoid discipline discrepancy
    zrodlo.dyscyplina_zrodla_set.create(dyscyplina=dyscyplina_1_01, rok=2023)
    zrodlo.dyscyplina_zrodla_set.create(dyscyplina=dyscyplina_2_03, rok=2023)

    komparator = KomparatorZrodelPBN(min_rok=2022, show_progress=False)
    stats = komparator.run()

    assert stats["processed"] == 1
    assert stats["points_discrepancies"] >= 1

    # Check that discrepancy was recorded
    rozbieznosc = RozbieznoscZrodlaPBN.objects.get(zrodlo=zrodlo, rok=2023)
    assert rozbieznosc.ma_rozbieznosc_punktow is True
    assert rozbieznosc.punkty_bpp == Decimal("50.00")
    assert rozbieznosc.punkty_pbn == Decimal("100.00")


@pytest.mark.django_db(transaction=True)
def test_komparator_finds_discipline_discrepancy(
    pbn_journal_with_data, dyscyplina_1_01, dyscyplina_2_03
):
    """Test that komparator finds discrepancy when BPP disciplines differ from PBN."""
    zrodlo = baker.make(Zrodlo, nazwa="Test Journal", pbn_uid=pbn_journal_with_data)

    # Create BPP punktacja matching PBN
    Punktacja_Zrodla.objects.create(
        zrodlo=zrodlo, rok=2023, punkty_kbn=Decimal("100.00")
    )

    # Add only one discipline (should have two from PBN)
    zrodlo.dyscyplina_zrodla_set.create(dyscyplina=dyscyplina_1_01, rok=2023)

    komparator = KomparatorZrodelPBN(min_rok=2022, show_progress=False)
    stats = komparator.run()

    assert stats["processed"] == 1
    assert stats["discipline_discrepancies"] >= 1

    # Check that discrepancy was recorded
    rozbieznosc = RozbieznoscZrodlaPBN.objects.get(zrodlo=zrodlo, rok=2023)
    assert rozbieznosc.ma_rozbieznosc_dyscyplin is True
    assert "1.1" in rozbieznosc.dyscypliny_bpp
    assert "2.3" not in rozbieznosc.dyscypliny_bpp  # Missing in BPP


@pytest.mark.django_db(transaction=True)
def test_komparator_no_discrepancy_when_data_matches(
    pbn_journal_with_data, dyscyplina_1_01, dyscyplina_2_03
):
    """Test that komparator doesn't create discrepancy when data matches."""
    zrodlo = baker.make(Zrodlo, nazwa="Test Journal", pbn_uid=pbn_journal_with_data)

    # Create BPP punktacja matching PBN
    Punktacja_Zrodla.objects.create(
        zrodlo=zrodlo, rok=2023, punkty_kbn=Decimal("100.00")
    )

    # Add both disciplines matching PBN
    zrodlo.dyscyplina_zrodla_set.create(dyscyplina=dyscyplina_1_01, rok=2023)
    zrodlo.dyscyplina_zrodla_set.create(dyscyplina=dyscyplina_2_03, rok=2023)

    komparator = KomparatorZrodelPBN(min_rok=2022, show_progress=False)
    stats = komparator.run()

    assert stats["processed"] == 1

    # No discrepancy for 2023
    assert not RozbieznoscZrodlaPBN.objects.filter(zrodlo=zrodlo, rok=2023).exists()


@pytest.mark.django_db(transaction=True)
def test_komparator_clears_existing_when_requested(pbn_journal_with_data):
    """Test that komparator clears existing discrepancies when clear_existing=True."""
    zrodlo = baker.make(Zrodlo, nazwa="Test Journal", pbn_uid=pbn_journal_with_data)

    # Create an old discrepancy
    RozbieznoscZrodlaPBN.objects.create(
        zrodlo=zrodlo,
        rok=2020,  # Old year that won't be processed
        ma_rozbieznosc_punktow=True,
    )

    komparator = KomparatorZrodelPBN(
        min_rok=2022, clear_existing=True, show_progress=False
    )
    komparator.run()

    # Old discrepancy should be deleted
    assert not RozbieznoscZrodlaPBN.objects.filter(zrodlo=zrodlo, rok=2020).exists()


@pytest.mark.django_db(transaction=True)
def test_komparator_skips_zrodlo_without_pbn_uid():
    """Test that komparator skips sources without PBN UID."""
    zrodlo = baker.make(Zrodlo, nazwa="Test Journal Without PBN", pbn_uid=None)

    komparator = KomparatorZrodelPBN(min_rok=2022, show_progress=False)
    stats = komparator.run()

    # Should not have processed this source
    assert stats["processed"] == 0
    assert not RozbieznoscZrodlaPBN.objects.filter(zrodlo=zrodlo).exists()
