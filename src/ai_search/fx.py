import logging
from decimal import Decimal

import requests
from django.conf import settings
from django.core.cache import cache

logger = logging.getLogger(__name__)

_CACHE_KEY = "ai_search:fx:usdpln"
_NBP_URL = "https://api.nbp.pl/api/exchangerates/rates/A/USD/?format=json"


def _fetch_nbp() -> Decimal:
    resp = requests.get(_NBP_URL, timeout=10)
    resp.raise_for_status()
    mid = resp.json()["rates"][0]["mid"]
    return Decimal(str(mid)).quantize(Decimal("0.0001"))


def usd_to_pln_rate() -> Decimal:
    """Kurs USD->PLN. Kolejność: cache Redis -> NBP -> DB FxRate -> stała.

    Nigdy nie podnosi wyjątku — FX nie może zablokować feature'a; do wyceny
    wystarczy ostatni znany / konserwatywny kurs.
    """
    from ai_search.models import FxRate

    cached = cache.get(_CACHE_KEY)
    if cached is not None:
        return Decimal(cached)

    try:
        rate = _fetch_nbp()
        cache.set(_CACHE_KEY, str(rate), settings.BPP_AI_FX_CACHE_TTL)
        FxRate.store(rate)
        return rate
    except (
        requests.RequestException,
        OSError,
        LookupError,
        TypeError,
        ValueError,
        ArithmeticError,
    ) as exc:
        # LookupError = KeyError + IndexError (brakujące/puste "rates"),
        # ArithmeticError = decimal.InvalidOperation (mid=null/nieliczbowe),
        # TypeError = nie-lista/skalar w JSON — wszystko degraduje do fallbacku.
        logger.warning("NBP FX niedostępny (%s), używam fallbacku", exc)

    last = FxRate.latest()
    if last is not None:
        return last.rate
    return Decimal(settings.BPP_AI_FX_FALLBACK)
