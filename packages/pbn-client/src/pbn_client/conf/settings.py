"""Environment defaults for the standalone PBN client.

Applications should normally pass credentials and timeouts to the transport
constructor. These variables remain available for command-line compatibility.
No framework settings object is imported here.
"""

from __future__ import annotations

import os
from collections.abc import Sequence

from pbn_client.const import DEFAULT_BASE_URL

Timeout = float | tuple[float, float]
DEFAULT_HTTP_TIMEOUT: Timeout = (30.0, 120.0)


def parse_timeout(
    raw: str | float | Sequence[float] | None,
    default: Timeout = DEFAULT_HTTP_TIMEOUT,
) -> Timeout:
    """Parse a requests timeout from a scalar or ``connect,read`` value."""

    if raw is None:
        return default
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, Sequence) and not isinstance(raw, str):
        values = tuple(float(value) for value in raw)
        return values if len(values) == 2 else default

    parts = [part.strip() for part in str(raw).split(",") if part.strip()]
    if len(parts) == 1:
        return float(parts[0])
    if len(parts) == 2:
        return (float(parts[0]), float(parts[1]))
    return default


PBN_CLIENT_DEFAULT_BASE_URL = DEFAULT_BASE_URL
PBN_CLIENT_APP_ID = os.getenv("PBN_CLIENT_APP_ID")
PBN_CLIENT_APP_TOKEN = os.getenv("PBN_CLIENT_APP_TOKEN")
PBN_CLIENT_BASE_URL = os.getenv("PBN_CLIENT_BASE_URL", DEFAULT_BASE_URL)
PBN_CLIENT_USER_TOKEN = os.getenv("PBN_CLIENT_USER_TOKEN")
PBN_CLIENT_HTTP_TIMEOUT = parse_timeout(os.getenv("PBN_CLIENT_HTTP_TIMEOUT"))
