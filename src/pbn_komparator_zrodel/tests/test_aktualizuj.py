"""Tests for aktualizuj_zrodlo_z_pbn update logic."""

from decimal import Decimal

import pytest
from model_bakery import baker

from bpp.models import Punktacja_Zrodla, Zrodlo

from ..models import LogAktualizacjiZrodla, RozbieznoscZrodlaPBN
from ..update_utils import aktualizuj_zrodlo_z_pbn


@pytest.mark.django_db
def test_aktualizuj_zrodlo_z_pbn_updates_points(
    pbn_journal_with_data, dyscyplina_1_01, dyscyplina_2_03
):
    """Test that aktualizuj_zrodlo_z_pbn updates points from PBN."""
    zrodlo = baker.make(Zrodlo, nazwa="Test Journal", pbn_uid=pbn_journal_with_data)

    # Create BPP punktacja with different value
    Punktacja_Zrodla.objects.create(
        zrodlo=zrodlo, rok=2023, punkty_kbn=Decimal("50.00")
    )

    # Run update
    result = aktualizuj_zrodlo_z_pbn(
        zrodlo,
        rok=2023,
        aktualizuj_punkty=True,
        aktualizuj_dyscypliny=False,
    )

    assert result is True

    # Check points were updated
    punktacja = zrodlo.punktacja_zrodla_set.get(rok=2023)
    assert punktacja.punkty_kbn == Decimal("100.00")

    # Check log was created
    log = LogAktualizacjiZrodla.objects.get(zrodlo=zrodlo, rok=2023)
    assert log.typ_zmiany == "punkty"


@pytest.mark.django_db
def test_aktualizuj_zrodlo_z_pbn_updates_disciplines(
    pbn_journal_with_data, dyscyplina_1_01, dyscyplina_2_03
):
    """Test that aktualizuj_zrodlo_z_pbn updates disciplines from PBN."""
    zrodlo = baker.make(Zrodlo, nazwa="Test Journal", pbn_uid=pbn_journal_with_data)

    # Create BPP punktacja
    Punktacja_Zrodla.objects.create(
        zrodlo=zrodlo, rok=2023, punkty_kbn=Decimal("100.00")
    )

    # Add only one discipline
    zrodlo.dyscyplina_zrodla_set.create(dyscyplina=dyscyplina_1_01, rok=2023)

    # Run update for disciplines only
    result = aktualizuj_zrodlo_z_pbn(
        zrodlo,
        rok=2023,
        aktualizuj_punkty=False,
        aktualizuj_dyscypliny=True,
    )

    assert result is True

    # Check disciplines were updated
    dyscypliny = set(
        zrodlo.dyscyplina_zrodla_set.filter(rok=2023).values_list(
            "dyscyplina__kod", flat=True
        )
    )
    assert dyscypliny == {"1.1", "2.3"}

    # Check log was created
    log = LogAktualizacjiZrodla.objects.get(zrodlo=zrodlo, rok=2023)
    assert log.typ_zmiany == "dyscypliny"


@pytest.mark.django_db
def test_aktualizuj_zrodlo_removes_discrepancy(
    pbn_journal_with_data, dyscyplina_1_01, dyscyplina_2_03
):
    """Test that aktualizuj_zrodlo_z_pbn removes discrepancy after update."""
    zrodlo = baker.make(Zrodlo, nazwa="Test Journal", pbn_uid=pbn_journal_with_data)

    # Create discrepancy
    RozbieznoscZrodlaPBN.objects.create(
        zrodlo=zrodlo,
        rok=2023,
        ma_rozbieznosc_punktow=True,
        punkty_bpp=Decimal("50.00"),
        punkty_pbn=Decimal("100.00"),
    )

    # Create BPP punktacja
    Punktacja_Zrodla.objects.create(
        zrodlo=zrodlo, rok=2023, punkty_kbn=Decimal("50.00")
    )

    # Run update
    aktualizuj_zrodlo_z_pbn(
        zrodlo, rok=2023, aktualizuj_punkty=True, aktualizuj_dyscypliny=False
    )

    # Discrepancy should be removed
    assert not RozbieznoscZrodlaPBN.objects.filter(zrodlo=zrodlo, rok=2023).exists()
