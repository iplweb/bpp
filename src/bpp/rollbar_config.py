import rollbar
from django.conf import settings
from rollbar.lib.transforms.scrub import ScrubTransform
from rollbar.lib.transforms.scruburl import ScrubUrlTransform

# Wyjątki, które Rollbar domyślnie rozbija na wiele itemów, bo zmienna treść
# w tracebacku (np. wyrenderowany raport z nazwiskiem autora w zmiennej
# lokalnej `html`) wycieka do fingerprintu. Dla nich narzucamy własny,
# stały fingerprint — patrz collapse_noisy_fingerprints.
NOISY_FINGERPRINT_EXC = {
    "DocxConversionError",
}

#: Domyślne `url_fields` pyrollbara — klucze, pod którymi spodziewa się URL-i.
#: `settings.ROLLBAR` ich nie nadpisuje, a `ScrubUrlTransform.in_scrub_fields`
#: i tak zwraca True dla każdego stringa; podajemy je dla zgodności.
URL_FIELDS = ("url", "link", "href")


class ScrubKoduAutoryzacyjnego(ScrubTransform):
    """Zamazuje pole ``code`` WSZĘDZIE POZA dwiema ścieżkami z linią kodu.

    Problem: ``code`` to jednocześnie nazwa parametru OAuth (kod autoryzacyjny
    — w POST do ``/o/token/`` oraz w GET do ``/orcid/callback/``, do
    zamazania) i nazwa pola, w którym pyrollbar trzyma LINIĘ KODU ŹRÓDŁOWEGO
    każdej ramki tracebacku (do zachowania).

    ``ScrubRedactTransform`` dopasowuje ścieżkę klucza po SUFIKSIE, więc
    ``"code"`` na liście ``scrub_fields`` trafiał w oba naraz i zamazywał całe
    tracebacki (patrz komentarz przy ``ROLLBAR_SCRUB_FIELDS``).

    Wyjątek jest zdefiniowany jako DOKŁADNA lista dwóch ścieżek, a nie jako
    „ścieżka zawiera ``frames``". Luźniejszy warunek dawał się obejść —
    ``request.POST.frames.code`` czy ``custom.frames[0].code`` przechodziłyby
    nietknięte — a co gorsza pomijał ``frames[N].locals.code``
    i ``frames[N].kwargs.code``, czyli DOKŁADNIE ten sekret, dla którego
    ``"code"`` w ogóle trafiło na listę: w django-oauth-toolkit ``code`` jest
    parametrem kilkunastu metod walidatora (``validate_code``,
    ``invalidate_authorization_code``, ``save_authorization_code``…), więc
    wyjątek w którejkolwiek z nich wystawiłby aktywny kod w zmiennych
    lokalnych ramki.
    """

    @staticmethod
    def _czy_linia_kodu_ramki(key):
        """Czy to JEDNA z dwóch ścieżek, pod którymi pyrollbar trzyma kod.

        Kształty zrzucone z działającego łańcucha transformów:
        ``("body", "trace", "frames", <int>, "code")`` oraz
        ``("body", "trace_chain", <int>, "frames", <int>, "code")``.
        """
        if len(key) == 5 and key[:3] == ("body", "trace", "frames"):
            return isinstance(key[3], int)
        if len(key) == 6 and key[:2] == ("body", "trace_chain"):
            return (
                isinstance(key[2], int)
                and key[3] == "frames"
                and isinstance(key[4], int)
            )
        return False

    def in_scrub_fields(self, key):
        # Case-insensitive jak `build_key_matcher` pyrollbara — bez tego
        # `POST.Code` / `POST.CODE` przestałyby być zamazywane.
        if not key or str(key[-1]).lower() != "code":
            return False
        return not self._czy_linia_kodu_ramki(tuple(key))


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
    pola = list(ustawienia.get("scrub_fields") or [])

    wlasne = list(ustawienia.get("custom_transforms") or [])
    wlasne.append(ScrubKoduAutoryzacyjnego(redact_char="*"))
    # Wbudowany ScrubUrlTransform pyrollbara czyści parametry w URL-ach na
    # podstawie `scrub_fields` (`params_to_scrub=SETTINGS['scrub_fields']`),
    # więc zdjęcie stamtąd "code" odebrałoby mu wiedzę o TYM parametrze —
    # a `?code=` w URL-u to realny wektor: /orcid/callback/ dostaje kod
    # autoryzacyjny w query stringu, a pyrollbar zapisuje pełny
    # `request.build_absolute_uri()` (także w nagłówku Referer i w zmiennych
    # lokalnych). Dokładamy więc własny ScrubUrlTransform, który zna "code".
    wlasne.append(
        ScrubUrlTransform(
            suffixes=[(pole,) for pole in URL_FIELDS],
            params_to_scrub=pola + ["code"],
        )
    )
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
