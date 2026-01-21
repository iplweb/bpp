import rollbar
from django.conf import settings


def add_hostname_to_payload(payload, **kw):
    """
    Global payload handler that adds DJANGO_BPP_HOSTNAME to all Rollbar payloads.
    This ensures every error report identifies which server generated it.
    """
    if "data" in payload:
        if "custom" not in payload["data"]:
            payload["data"]["custom"] = {}
        payload["data"]["custom"]["DJANGO_BPP_HOSTNAME"] = getattr(
            settings, "DJANGO_BPP_HOSTNAME", "unknown"
        )
    return payload


_initialized = False


def configure_rollbar():
    """
    Initialize Rollbar and register the hostname payload handler.
    Safe to call multiple times - only runs once.
    """
    global _initialized
    if _initialized:
        return

    rollbar.init(**settings.ROLLBAR)
    rollbar.events.add_payload_handler(add_hostname_to_payload)
    _initialized = True
