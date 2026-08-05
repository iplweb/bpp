from dataclasses import dataclass
from decimal import Decimal

from django.conf import settings
from django.db.models import Sum
from django.utils import timezone

from ai_search.models import AISearchQuery


@dataclass
class BudgetStatus:
    ok: bool
    reason: str | None = None


def _sum_since(dt) -> Decimal:
    agg = AISearchQuery.objects.filter(created__gte=dt).aggregate(s=Sum("cost_pln"))
    return agg["s"] or Decimal("0")


def spent_today() -> Decimal:
    now = timezone.localtime()
    start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    return _sum_since(start)


def spent_this_month() -> Decimal:
    now = timezone.localtime()
    start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    return _sum_since(start)


def check_budget() -> BudgetStatus:
    """Twardy blok, gdy dzienny lub miesięczny budżet PLN jest wyczerpany."""
    daily = Decimal(str(settings.BPP_AI_DAILY_BUDGET_PLN))
    monthly = Decimal(str(settings.BPP_AI_MONTHLY_BUDGET_PLN))
    if spent_today() >= daily:
        return BudgetStatus(
            ok=False,
            reason="Dzienny limit kosztów AI został osiągnięty. "
            "Spróbuj jutro lub użyj „szukaj zapytaniem”.",
        )
    if spent_this_month() >= monthly:
        return BudgetStatus(
            ok=False,
            reason="Miesięczny limit kosztów AI został osiągnięty. "
            "Użyj „szukaj zapytaniem”.",
        )
    return BudgetStatus(ok=True)
