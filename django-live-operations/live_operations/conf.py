from django.conf import settings

_DEFAULTS = {
    "BASE_TEMPLATE": "base.html",
    "RUNNER": "eager",
    "THROTTLE_HZ": 10,
}


def get_setting(key: str, default=None):
    """Read a value from settings.LIVE_OPERATIONS dict with fallback to _DEFAULTS."""
    live_ops = getattr(settings, "LIVE_OPERATIONS", {})
    if key in live_ops:
        return live_ops[key]
    if default is not None:
        return default
    return _DEFAULTS.get(key)
