from decimal import Decimal

import pytest
from model_bakery import baker

from ai_search import budget
from ai_search.models import AISearchQuery


@pytest.mark.django_db
def test_ok_when_under_budget(settings):
    settings.BPP_AI_DAILY_BUDGET_PLN = "10"
    settings.BPP_AI_MONTHLY_BUDGET_PLN = "100"
    baker.make(AISearchQuery, cost_pln=Decimal("2"))
    status = budget.check_budget()
    assert status.ok is True


@pytest.mark.django_db
def test_blocks_when_daily_exceeded(settings):
    settings.BPP_AI_DAILY_BUDGET_PLN = "5"
    settings.BPP_AI_MONTHLY_BUDGET_PLN = "100"
    baker.make(AISearchQuery, cost_pln=Decimal("6"))
    status = budget.check_budget()
    assert status.ok is False
    assert "dzien" in status.reason.lower() or "dzień" in status.reason.lower()


@pytest.mark.django_db
def test_blocks_when_monthly_exceeded(settings):
    settings.BPP_AI_DAILY_BUDGET_PLN = "1000"
    settings.BPP_AI_MONTHLY_BUDGET_PLN = "5"
    baker.make(AISearchQuery, cost_pln=Decimal("6"))
    status = budget.check_budget()
    assert status.ok is False
    assert "mies" in status.reason.lower()
