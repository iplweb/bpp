from datetime import date
from decimal import Decimal

from django.conf import settings

_MILLION = Decimal("1000000")


def _price(cfg: dict, key: str, at_date: date) -> Decimal:
    """Cena input/output per 1M tokenów, z uwzględnieniem intro-pricingu."""
    intro_until = cfg.get("intro_until")
    if intro_until and at_date <= date.fromisoformat(intro_until):
        return Decimal(cfg[f"intro_{key}"])
    return Decimal(cfg[key])


def cost_usd_from_usage(usage: dict, model: str, at_date: date) -> Decimal:
    """Koszt (USD, Decimal) danego wywołania na podstawie usage i cennika.

    ``usage`` klucze: input_tokens, output_tokens, cache_read_tokens,
    cache_write_tokens. Podnosi KeyError dla nieznanego modelu — brak ceny to
    błąd, nie cichy koszt zero (patrz spec, KRYT. #1).
    """
    cfg = settings.BPP_AI_PRICING[model]
    in_price = _price(cfg, "input", at_date)
    out_price = _price(cfg, "output", at_date)
    read_mult = Decimal(cfg["cache_read_mult"])
    write_mult = Decimal(cfg["cache_write_mult"])

    total = (
        Decimal(usage.get("input_tokens", 0)) * in_price
        + Decimal(usage.get("output_tokens", 0)) * out_price
        + Decimal(usage.get("cache_read_tokens", 0)) * in_price * read_mult
        + Decimal(usage.get("cache_write_tokens", 0)) * in_price * write_mult
    ) / _MILLION
    return total.quantize(Decimal("0.000001"))
