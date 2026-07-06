import os

from django.conf import settings

PBN_CLIENT_DEFAULT_BASE_URL = "https://pbn-micro-alpha.opi.org.pl"


PBN_CLIENT_APP_ID = getattr(
    settings, "PBN_CLIENT_APP_ID", os.getenv("PBN_CLIENT_APP_ID")
)


PBN_CLIENT_APP_TOKEN = getattr(
    settings, "PBN_CLIENT_APP_TOKEN", os.getenv("PBN_CLIENT_APP_TOKEN")
)


PBN_CLIENT_BASE_URL = getattr(
    settings,
    "PBN_CLIENT_BASE_URL",
    os.getenv("PBN_CLIENT_BASE_URL", PBN_CLIENT_DEFAULT_BASE_URL),
)

PBN_CLIENT_USER_TOKEN = getattr(
    settings, "PBN_CLIENT_USER_TOKEN", os.getenv("PBN_CLIENT_USER_TOKEN")
)


def _parse_timeout(raw, default):
    if raw is None:
        return default
    if isinstance(raw, (int, float)):
        return float(raw)
    if isinstance(raw, (tuple, list)):
        return tuple(float(x) for x in raw)
    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
    if len(parts) == 1:
        return float(parts[0])
    if len(parts) == 2:
        return (float(parts[0]), float(parts[1]))
    return default


PBN_CLIENT_HTTP_TIMEOUT = _parse_timeout(
    getattr(
        settings,
        "PBN_CLIENT_HTTP_TIMEOUT",
        os.getenv("PBN_CLIENT_HTTP_TIMEOUT"),
    ),
    default=(30.0, 120.0),
)
