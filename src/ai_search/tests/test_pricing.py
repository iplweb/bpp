from datetime import date
from decimal import Decimal

from ai_search.pricing import cost_usd_from_usage

USAGE = {
    "input_tokens": 1_000_000,
    "output_tokens": 100_000,
    "cache_read_tokens": 0,
    "cache_write_tokens": 0,
}


def test_intro_pricing_before_cutoff():
    # intro: input 2.0, output 10.0 -> 2 + 1 = 3.0 USD
    cost = cost_usd_from_usage(USAGE, "claude-sonnet-5", date(2026, 7, 1))
    assert cost == Decimal("3.000000")


def test_standard_pricing_after_cutoff():
    # standard: input 3.0, output 15.0 -> 3 + 1.5 = 4.5 USD
    cost = cost_usd_from_usage(USAGE, "claude-sonnet-5", date(2026, 9, 1))
    assert cost == Decimal("4.500000")


def test_cache_read_and_write_multipliers():
    usage = {
        "input_tokens": 0,
        "output_tokens": 0,
        "cache_read_tokens": 1_000_000,
        "cache_write_tokens": 1_000_000,
    }
    # standard input 3.0; read 0.1x=0.3, write 1.25x=3.75 -> 4.05
    cost = cost_usd_from_usage(usage, "claude-sonnet-5", date(2026, 9, 1))
    assert cost == Decimal("4.050000")


def test_unknown_model_raises():
    import pytest

    with pytest.raises(KeyError):
        cost_usd_from_usage(USAGE, "no-such-model", date(2026, 9, 1))
