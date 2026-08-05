from decimal import Decimal

import pytest
from model_bakery import baker

from ai_search.models import AISearchQuery, FxRate


@pytest.mark.django_db
def test_aisearchquery_str():
    q = baker.make(AISearchQuery, pytanie="ksiazki po 2020")
    assert "ksiazki po 2020" in str(q)


@pytest.mark.django_db
def test_fxrate_store_and_latest():
    assert FxRate.latest() is None
    FxRate.store("4.12")
    FxRate.store("4.20")
    assert FxRate.latest().rate == Decimal("4.2000")
