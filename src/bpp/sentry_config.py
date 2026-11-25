"""Inicjalizacja Sentry SDK (dla GlitchTip — serwer mówiący protokołem Sentry).

Odpowiednik :mod:`bpp.rollbar_config`. Sentry startuje WYŁĄCZNIE, gdy
``settings.SENTRY_DSN`` jest niepusty; bez niego ten moduł nic nie robi,
a BPP zachowuje się dokładnie jak przed dodaniem Sentry (sam Rollbar).

Co Sentry łapie (dobrane tak, by odpowiadało temu, co dziś trafia do Rollbara):

* nieobsłużone wyjątki widoków — ``DjangoIntegration``
  (Rollbar: ``CustomRollbarNotifierMiddleware``),
* błędy zadań Celery — ``CeleryIntegration`` (Rollbar: sygnał
  ``task_failure`` w ``django_bpp.celery_tasks``, który dlatego woła
  ``capture_exception(..., pomin_sentry=True)``),
* wpisy ERROR z loggerów, które mają podpięty handler ``sentry``
  w ``LOGGING`` (Rollbar: handler ``rollbar``). Globalne zamienianie każdego
  ``logger.error`` w zdarzenie jest WYŁĄCZONE (``event_level=None``) —
  Rollbar też tego nie robi, a ``zaloguj_polkniety_wyjatek`` zgłasza wyjątek
  sam, więc dostalibyśmy duplikaty,
* jawne zgłoszenia z kodu — :mod:`bpp.zglaszanie_bledow`.

Filtry wyjątków (``django_bpp.rollbar_filters``) obowiązują oba backendy:
``before_send`` czyta tę samą listę z ``settings.ROLLBAR``.

Dane osobowe czyścimy dwiema warstwami:

1. ``EventScrubber`` z SDK — po NAZWIE klucza (hasła, tokeny, ciasteczka),
2. silnik Relay z Sentry (pakiet ``sentry-relay``, ten sam kod w Ruście,
   którego używa sentry.io) — po WARTOŚCI: e-maile, adresy IP, PESEL,
   numery kart, IBAN, tokeny ``Bearer``, hasła w URL-ach, klucze PEM. Działa
   także na zmiennych lokalnych ramek (``repr`` obiektów), komunikatach
   wyjątków i breadcrumbs — zmienne lokalne zostają włączone celowo.

Relay działa w procesie (nie jako osobna usługa). Jeśli się wysypie,
zdarzenie idzie dalej oczyszczone tylko warstwą 1 i z tagiem
``bpp_pii_relay=blad`` — gubienie zgłoszeń błędów byłoby gorsze.
"""

import logging
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import sentry_sdk
from django.conf import settings
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration, ignore_logger
from sentry_sdk.scrubber import DEFAULT_DENYLIST, EventScrubber

from bpp.zglaszanie_bledow import POZIOMY_SENTRY
from django_bpp.version import VERSION

try:
    from sentry_relay.processing import pii_strip_event
except ImportError:  # brak wheela dla platformy — działamy bez warstwy 2
    pii_strip_event = None

logger = logging.getLogger(__name__)
# Komunikaty tego modułu NIE mogą wracać do Sentry: błąd w before_send
# zgłoszony przez handler ``sentry`` znów przeszedłby przez before_send.
ignore_logger(__name__)

#: Zamiennik zamazanej wartości w query stringach (jak w pyrollbarze).
ZAMAZANE = "********"

#: Gdzie NIE szukamy danych osobowych po wartości: kod źródłowy, ścieżki
#: plików i metadane SDK. Tam ich nie ma, a reguła ``@ip`` cięłaby numery
#: wersji, czyniąc traceback i opis środowiska mylącymi.
_POZA_DANYMI = (
    "debug_meta.** || $frame.filename || $frame.abs_path || $frame.module"
    " || $frame.function || $frame.context_line || $frame.pre_context.**"
    " || $frame.post_context.** || $sdk.** || modules.** || release"
)

#: Konfiguracja Relaya (format ``piiConfig`` z Sentry). Reguły ``@…`` są
#: wbudowane w Relay; ``pesel`` i ``nrb`` są nasze:
#:
#: * PESEL łapiemy samym wzorcem 11 cyfr (Relay nie sprawdzi sumy
#:   kontrolnej) — zamaże też np. numer telefonu z prefiksem 48, co
#:   z punktu widzenia RODO jest w porządku,
#: * ``@iban`` nie łapie numeru konta zapisanego w grupach ze spacjami
#:   (``PL61 1090 1014 …``), czyli tak, jak wpisują go ludzie.
#:
#: UWAGA: nieznana nazwa reguły przechodzi w Relayu po cichu i po prostu
#: nic nie czyści, a błędny selektor wywraca całe czyszczenie (zdarzenie
#: idzie wtedy z tagiem ``bpp_pii_relay=blad``) — każda reguła musi mieć
#: przypadek w ``test_sentry_dane_osobowe.py``.
KONFIGURACJA_PII = {
    "rules": {
        "pesel": {
            "type": "pattern",
            "pattern": r"\b\d{11}\b",
            "redaction": {"method": "replace", "text": "[pesel]"},
        },
        "nrb": {
            "type": "pattern",
            "pattern": r"\b(?:PL ?)?\d{2}(?: ?\d{4}){6}\b",
            "redaction": {"method": "replace", "text": "[nrb]"},
        },
    },
    "applications": {
        f"$string && !({_POZA_DANYMI})": [
            "@email:replace",
            "@ip:replace",
            "@creditcard:replace",
            "@iban:replace",
            "@bearer:replace",
            "@urlauth:replace",
            "@pemkey:replace",
            "nrb",
            "pesel",
        ],
    },
}

_initialized = False


def wyczysc_dane_osobowe(event, konfiguracja=None):
    """Czyści dane osobowe po wartości silnikiem Relay (warstwa 2).

    Nigdy nie gubi zdarzenia: gdy Relay jest niedostępny albo się wysypie,
    zwraca zdarzenie bez tej warstwy (``EventScrubber`` już przeszedł),
    z tagiem ``bpp_pii_relay``, żeby było to widać w GlitchTipie.
    """
    if konfiguracja is None:
        konfiguracja = KONFIGURACJA_PII

    if pii_strip_event is None:
        _oznacz(event, "brak")
        return event

    try:
        wynik = pii_strip_event(konfiguracja, event)
    except Exception:
        # Celowo szeroko: biblioteka w Ruście rzuca własne wyjątki, a błąd
        # serializacji też ma nie zabić zgłoszenia. Logujemy z tracebackiem
        # (logger wyłączony z Sentry — patrz ignore_logger wyżej).
        logger.exception(
            "Czyszczenie danych osobowych (Relay) nie powiodło się; "
            "zdarzenie idzie bez tej warstwy"
        )
        _oznacz(event, "blad")
        return event

    # _meta to adnotacje Relaya „co wycięto” — GlitchTip ich nie pokazuje.
    wynik.pop("_meta", None)
    # Relay normalizuje tagi do listy par; reszta BPP (i testy) zakłada
    # słownik, który SDK wysyła zawsze — wracamy do tej postaci.
    tagi = wynik.get("tags")
    if isinstance(tagi, list):
        wynik["tags"] = {
            para[0]: para[1]
            for para in tagi
            if isinstance(para, list) and len(para) == 2
        }
    return wynik


def _oznacz(event, stan):
    tagi = event.setdefault("tags", {})
    if isinstance(tagi, dict):
        tagi["bpp_pii_relay"] = stan


def lista_pol_do_zamazania():
    """Pola wrażliwe: domyślne Sentry + nasza lista dla Rollbara + ``code``.

    ``code`` (kod autoryzacyjny OAuth) w Rollbarze wymaga osobnego transformu,
    bo pyrollbar trzyma pod tą nazwą linię kodu ramki tracebacku. Sentry
    trzyma ją pod ``context_line``, więc tu wystarczy zwykły wpis na liście.
    """
    pola = list(DEFAULT_DENYLIST)
    pola += settings.ROLLBAR.get("scrub_fields") or []
    pola.append("code")
    # bez duplikatów, z zachowaniem kolejności
    return list(dict.fromkeys(pole.lower() for pole in pola))


def zamaz_parametry_url(wartosc, pola):
    """Zamazuje wartości wrażliwych parametrów w URL-u lub query stringu.

    EventScrubber Sentry czyści słowniki (dane POST, nagłówki, ciasteczka,
    zmienne ramek), ale NIE parametry w ``query_string`` ani w nagłówku
    ``Referer`` — a tam bywa ``?code=`` z /orcid/callback/.
    """
    if not isinstance(wartosc, str) or not wartosc:
        return wartosc

    czy_url = "?" in wartosc or "://" in wartosc
    if czy_url:
        czesci = urlsplit(wartosc)
        query = czesci.query
    else:
        query = wartosc

    if not query:
        return wartosc

    pary = parse_qsl(query, keep_blank_values=True)
    if not any(klucz.lower() in pola for klucz, _ in pary):
        return wartosc

    nowe = urlencode(
        [(k, ZAMAZANE if k.lower() in pola else v) for k, v in pary],
        safe="*",
    )
    if czy_url:
        return urlunsplit(czesci._replace(query=nowe))
    return nowe


def _zamaz_request(request, pola):
    """Zamazuje parametry w ``query_string`` i nagłówku ``Referer`` zdarzenia."""
    if not isinstance(request, dict):
        return
    if "query_string" in request:
        request["query_string"] = zamaz_parametry_url(request["query_string"], pola)
    naglowki = request.get("headers")
    if isinstance(naglowki, dict):
        for nazwa in list(naglowki):
            if nazwa.lower() == "referer":
                naglowki[nazwa] = zamaz_parametry_url(naglowki[nazwa], pola)


def _poziom_z_filtrow(exc, filtry):
    for klasa, poziom in filtry:
        if isinstance(exc, klasa):
            return poziom
    return None


def zbuduj_before_send(filtry, pola, hostname):
    """Zwraca hook ``before_send`` dla ``sentry_sdk.init``.

    :param filtry: lista ``(klasa_wyjątku, poziom)`` w formacie
        ``ROLLBAR["exception_level_filters"]``; poziom ``"ignored"`` = nie
        wysyłaj wcale, inny = nadpisz poziom zdarzenia.
    :param pola: pola wrażliwe (małe litery) do zamazania w query stringach.
    :param hostname: ``DJANGO_BPP_HOSTNAME`` — tag identyfikujący instalację
        (w Rollbarze ``custom.DJANGO_BPP_HOSTNAME``).
    """

    def before_send(event, hint):
        exc_info = (hint or {}).get("exc_info")
        if exc_info and exc_info[1] is not None:
            poziom = _poziom_z_filtrow(exc_info[1], filtry)
            if poziom == "ignored":
                return None
            if poziom is not None:
                event["level"] = POZIOMY_SENTRY.get(poziom, poziom)

        event.setdefault("tags", {})
        if isinstance(event["tags"], dict):
            event["tags"].setdefault("DJANGO_BPP_HOSTNAME", hostname)

        _zamaz_request(event.get("request"), pola)
        return wyczysc_dane_osobowe(event)

    return before_send


def opcje_sentry():
    """Argumenty dla ``sentry_sdk.init`` wyliczone z ustawień Django."""
    pola = lista_pol_do_zamazania()
    send_default_pii = bool(getattr(settings, "SENTRY_SEND_DEFAULT_PII", False))
    traces = float(getattr(settings, "SENTRY_TRACES_SAMPLE_RATE", 0.0) or 0.0)
    srodowisko = getattr(settings, "SENTRY_ENVIRONMENT", "") or settings.ROLLBAR.get(
        "environment", "development"
    )

    return {
        "dsn": settings.SENTRY_DSN,
        "environment": srodowisko,
        "release": VERSION,
        # None (a nie 0.0) = śledzenie wydajności całkiem wyłączone, bez
        # tworzenia niewysyłanych transakcji.
        "traces_sample_rate": traces if traces > 0 else None,
        "send_default_pii": send_default_pii,
        # Tylko integracje wymienione niżej (+ domyślne: dedupe, excepthook,
        # stdlib…). Automatyczne włączanie WYŁĄCZONE: m.in. integracje MCP
        # i Starlette łapałyby wyjątki narzędzi MCP, które mcp_server celowo
        # NIE zgłasza (BppError, limitowanie zgłoszeń przy awariach — patrz
        # mcp_server.aplikacja / routing), czyli otwierałyby anonimowy kanał
        # wyczerpujący kwotę serwera.
        "auto_enabling_integrations": False,
        "integrations": [
            DjangoIntegration(),
            CeleryIntegration(),
            LoggingIntegration(level=logging.INFO, event_level=None),
        ],
        "event_scrubber": EventScrubber(
            denylist=pola,
            recursive=True,
            send_default_pii=send_default_pii,
        ),
        "before_send": zbuduj_before_send(
            settings.ROLLBAR.get("exception_level_filters") or [],
            set(pola),
            getattr(settings, "DJANGO_BPP_HOSTNAME", "unknown"),
        ),
    }


def configure_sentry():
    """Zainicjalizuj Sentry, jeśli ``SENTRY_DSN`` jest ustawiony.

    Bezpieczne przy wielokrotnym wywołaniu. Zwraca True, gdy Sentry działa.
    """
    global _initialized
    if _initialized:
        return True

    if not getattr(settings, "SENTRY_DSN", ""):
        return False

    sentry_sdk.init(**opcje_sentry())
    _initialized = True
    return True
