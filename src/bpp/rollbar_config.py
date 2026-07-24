import rollbar
from django.conf import settings

# Wyjątki, które Rollbar domyślnie rozbija na wiele itemów, bo zmienna treść
# w tracebacku (np. wyrenderowany raport z nazwiskiem autora w zmiennej
# lokalnej `html`) wycieka do fingerprintu. Dla nich narzucamy własny,
# stały fingerprint — patrz collapse_noisy_fingerprints.
NOISY_FINGERPRINT_EXC = {
    "DocxConversionError",
}


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


def collapse_noisy_fingerprints(payload, **kw):
    """Narzuć stały fingerprint na zgłośne wyjątki (patrz NOISY_FINGERPRINT_EXC).

    Rollbar domyślnie tworzy osobny item per raport, bo treść HTML z danymi
    autora trafia do fingerprintu. Jawny ``data["fingerprint"]`` przejmuje
    grupowanie: jeden serwer z zepsutą konwersją = dokładnie jeden item,
    niezależnie od liczby autorów. Klucz ``(klasa, host)``, żeby dwa różne
    serwery pozostały dwoma osobnymi itemami (dwa problemy do naprawy).

    Musi być zarejestrowany PO add_hostname_to_payload — czyta hosta z
    ``custom`` wypełnionego przez tamten handler.
    """
    data = payload.get("data", {})
    body = data.get("body", {})
    chain = body.get("trace_chain")
    # trace_chain[0] to najbardziej zewnętrzny (finalnie podniesiony) wyjątek;
    # dla niełańcuchowych zgłoszeń bierzemy pojedynczy trace.
    trace = chain[0] if chain else body.get("trace")
    if not trace:
        return payload
    exc_class = trace.get("exception", {}).get("class")
    if exc_class in NOISY_FINGERPRINT_EXC:
        host = data.get("custom", {}).get("DJANGO_BPP_HOSTNAME", "unknown")
        data["fingerprint"] = f"{exc_class}:{host}"
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
    # PO hostname: collapse_noisy_fingerprints czyta hosta z custom.
    rollbar.events.add_payload_handler(collapse_noisy_fingerprints)
    _initialized = True
