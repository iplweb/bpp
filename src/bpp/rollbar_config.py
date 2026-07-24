import rollbar
from django.conf import settings
from rollbar.lib.transforms.scrub import ScrubTransform

# Wyjątki, które Rollbar domyślnie rozbija na wiele itemów, bo zmienna treść
# w tracebacku (np. wyrenderowany raport z nazwiskiem autora w zmiennej
# lokalnej `html`) wycieka do fingerprintu. Dla nich narzucamy własny,
# stały fingerprint — patrz collapse_noisy_fingerprints.
NOISY_FINGERPRINT_EXC = {
    "DocxConversionError",
}


class ScrubKoduAutoryzacyjnego(ScrubTransform):
    """Zamazuje pole ``code``, ale NIE w ramkach stosu.

    Problem: ``code`` to jednocześnie nazwa parametru OAuth (kod autoryzacyjny
    w POST do ``/o/token/``, do zamazania) i nazwa pola, w którym pyrollbar
    trzyma LINIĘ KODU ŹRÓDŁOWEGO każdej ramki tracebacku (do zachowania).

    ``ScrubRedactTransform`` dopasowuje ścieżkę klucza po SUFIKSIE, więc
    ``"code"`` na liście ``scrub_fields`` trafiał w oba naraz. Od pyrollbara
    1.4.0 skutkowało to tym, że KAŻDY traceback w Rollbarze miał wszystkie
    linie kodu zamazane na ``"****"`` — czyli każde śledztwo zaczynało się bez
    najważniejszej informacji. (Porównaj item #379 na pyrollbarze 1.3.0, gdzie
    kod jest widoczny, z #1554 na 1.4.0, gdzie już nie.)

    Rozwiązanie: ``"code"`` znika z ``ROLLBAR_SCRUB_FIELDS``, a zamazywanie
    przejmuje ten transform, który patrzy na CAŁĄ ścieżkę klucza i odpuszcza,
    gdy prowadzi ona przez ``frames`` — czyli przez traceback.

    Pozostałe pola (``password``, ``code_verifier``, ``refresh_token`` itd.)
    zostają na liście ``scrub_fields`` i są nadal zamazywane wszędzie, także
    w zmiennych lokalnych ramek.
    """

    def in_scrub_fields(self, key):
        if not key or key[-1] != "code":
            return False
        # ("body", "trace", "frames", 0, "code") → linia kodu, zostawiamy.
        # ("request", "POST", "code")            → sekret OAuth, zamazujemy.
        return "frames" not in key


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


def ustawienia_rollbara():
    """``settings.ROLLBAR`` wzbogacone o nasze własne transformy payloadu.

    Transform dokładamy TUTAJ, a nie w ``settings.ROLLBAR``, żeby nie
    importować ``bpp.*`` na etapie ładowania ustawień — ``configure_rollbar``
    i tak biegnie z ``AppConfig.ready()`` (patrz ``bpp/apps.py``), czyli PRZED
    inicjalizacją middleware'u django-rollbar. To istotne: ``rollbar.init``
    buduje łańcuch transformów tylko przy PIERWSZYM wywołaniu, więc gdyby
    ubiegł nas middleware, nasz transform nigdy by nie wszedł.
    """
    ustawienia = dict(settings.ROLLBAR)
    wlasne = list(ustawienia.get("custom_transforms") or [])
    wlasne.append(ScrubKoduAutoryzacyjnego(redact_char="*"))
    ustawienia["custom_transforms"] = wlasne
    return ustawienia


def configure_rollbar():
    """
    Initialize Rollbar and register the hostname payload handler.
    Safe to call multiple times - only runs once.
    """
    global _initialized
    if _initialized:
        return

    rollbar.init(**ustawienia_rollbara())
    rollbar.events.add_payload_handler(add_hostname_to_payload)
    # PO hostname: collapse_noisy_fingerprints czyta hosta z custom.
    rollbar.events.add_payload_handler(collapse_noisy_fingerprints)
    _initialized = True
