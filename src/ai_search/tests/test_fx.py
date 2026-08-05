from decimal import Decimal
from unittest import mock

import pytest
from django.core.cache import cache

from ai_search import fx
from ai_search.models import FxRate


@pytest.fixture(autouse=True)
def _locmem_cache(settings):
    caches = dict(settings.CACHES)
    caches["default"] = {"BACKEND": "django.core.cache.backends.locmem.LocMemCache"}
    settings.CACHES = caches
    from django.core.cache import cache as cache_module

    cache_module.clear()
    yield cache_module
    cache_module.clear()


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.delete("ai_search:fx:usdpln")
    yield
    cache.delete("ai_search:fx:usdpln")


def _nbp_response(mid):
    m = mock.Mock()
    m.raise_for_status = mock.Mock()
    m.json.return_value = {"rates": [{"mid": mid}]}
    return m


def _raw_response(payload):
    """HTTP 200 z dowolnym (potencjalnie zniekształconym) ciałem JSON."""
    m = mock.Mock()
    m.raise_for_status = mock.Mock()
    m.json.return_value = payload
    return m


@pytest.mark.django_db
def test_fetches_from_nbp_and_persists():
    with mock.patch("ai_search.fx.requests.get", return_value=_nbp_response(4.11)):
        rate = fx.usd_to_pln_rate()
    assert rate == Decimal("4.1100")
    assert FxRate.latest().rate == Decimal("4.1100")


@pytest.mark.django_db
def test_uses_cache_without_second_http_call():
    with mock.patch("ai_search.fx.requests.get", return_value=_nbp_response(4.11)) as g:
        fx.usd_to_pln_rate()
        fx.usd_to_pln_rate()
    assert g.call_count == 1


@pytest.mark.django_db
def test_falls_back_to_db_when_nbp_down():
    FxRate.store("4.05")
    with mock.patch("ai_search.fx.requests.get", side_effect=OSError("boom")):
        rate = fx.usd_to_pln_rate()
    assert rate == Decimal("4.0500")


@pytest.mark.django_db
def test_terminal_fallback_when_nothing_available(settings):
    settings.BPP_AI_FX_FALLBACK = "4.5"
    with mock.patch("ai_search.fx.requests.get", side_effect=OSError("boom")):
        rate = fx.usd_to_pln_rate()
    assert rate == Decimal("4.5")


@pytest.mark.django_db
def test_empty_rates_list_falls_back_without_raising():
    """HTTP 200 z pustą listą ``rates`` (IndexError) nie może uciec —
    docstring gwarantuje „Nigdy nie podnosi wyjątku”."""
    FxRate.store("4.02")
    with mock.patch(
        "ai_search.fx.requests.get", return_value=_raw_response({"rates": []})
    ):
        rate = fx.usd_to_pln_rate()
    assert rate == Decimal("4.0200")


@pytest.mark.django_db
def test_null_mid_falls_back_without_raising():
    """HTTP 200 z ``mid=null`` → ``Decimal("None")`` (decimal.InvalidOperation,
    podklasa ArithmeticError, NIE ValueError) nie może uciec."""
    FxRate.store("4.03")
    with mock.patch(
        "ai_search.fx.requests.get",
        return_value=_raw_response({"rates": [{"mid": None}]}),
    ):
        rate = fx.usd_to_pln_rate()
    assert rate == Decimal("4.0300")


@pytest.mark.django_db
def test_rates_not_a_list_falls_back_without_raising(settings):
    """HTTP 200 z ``rates=null`` → ``None[0]`` (TypeError) nie może uciec."""
    settings.BPP_AI_FX_FALLBACK = "4.44"
    with mock.patch(
        "ai_search.fx.requests.get", return_value=_raw_response({"rates": None})
    ):
        rate = fx.usd_to_pln_rate()
    assert rate == Decimal("4.44")
