"""Testy modeli przeglądarki ewaluacji.

Ten moduł zawiera testy dla modelu StatusPrzegladarkaRecalc, który jest
singletonem używanym do śledzenia statusu przeliczania punktacji
w przeglądarce ewaluacji.
"""

import pytest
from model_bakery import baker

from bpp.models import Uczelnia
from ewaluacja_optymalizacja.models import StatusPrzegladarkaRecalc

# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def uczelnia(db):
    """Utwórz uczelnię testową."""
    return baker.make(Uczelnia, nazwa="Testowa Uczelnia")


# =============================================================================
# Testy modelu StatusPrzegladarkaRecalc
# =============================================================================


@pytest.mark.django_db
def test_status_przegladarka_recalc_singleton():
    """Test że StatusPrzegladarkaRecalc jest singletonem."""
    status1 = StatusPrzegladarkaRecalc.get_or_create()
    status2 = StatusPrzegladarkaRecalc.get_or_create()
    assert status1.pk == status2.pk == 1


@pytest.mark.django_db
def test_status_przegladarka_recalc_rozpocznij(uczelnia):
    """Test metody rozpocznij."""
    status = StatusPrzegladarkaRecalc.get_or_create()
    punkty_przed = {"1": 100.0, "2": 200.0}

    status.rozpocznij("test-task-123", uczelnia, punkty_przed)

    status.refresh_from_db()
    assert status.w_trakcie is True
    assert status.task_id == "test-task-123"
    assert status.uczelnia == uczelnia
    assert status.punkty_przed == punkty_przed
    assert status.data_rozpoczecia is not None


@pytest.mark.django_db
def test_status_przegladarka_recalc_zakoncz(uczelnia):
    """Test metody zakoncz."""
    status = StatusPrzegladarkaRecalc.get_or_create()
    status.rozpocznij("test-task", uczelnia, {})

    status.zakoncz("Zakończono pomyślnie")

    status.refresh_from_db()
    assert status.w_trakcie is False
    assert status.data_zakonczenia is not None
    assert status.ostatni_komunikat == "Zakończono pomyślnie"
