"""Logowanie do PBN na LOKALNEJ instancji BPP z przechwyceniem powrotu.

PBN po zalogowaniu odsyła przeglądarkę na adres zwrotny zapisany przy
aplikacji w PBN, czyli na serwer produkcyjny klienta
(``https://<serwer klienta>/pbn_api/callback?ott=<kod>``), a nie na
``localhost``. Tutaj prowadzimy przeglądarkę (Playwright, Chromium) przez
zwykłą ścieżkę „autoryzuj PBN API" lokalnego BPP i podmieniamy ten jeden
powrót: żądanie do obcego hosta jest zatrzymywane, ZANIM wyjdzie z
przeglądarki, i zastępowane przekierowaniem na ten sam ``path`` lokalnej
instancji. Autoryzację kończy lokalny BPP swoim normalnym widokiem.

⚠️ Przechwytywanie idzie przez CDP (domena ``Fetch``), a NIE przez
``context.route()`` Playwrighta. ``route()`` nie widzi kolejnych skoków
przekierowania (zmierzone: handler nie jest wołany, żądanie dociera do
obcego serwera), a powrót z PBN to właśnie przekierowanie 302 po wysłaniu
formularza logowania. Nie „upraszczaj" tego do ``route()`` — test e2e
(``test_logowanie_lokalne_e2e.py``) liczy żądania, które dotarły do
„obcego" serwera.

Kod korzystający z bazy (sesja, sprawdzenie tokenu) celowo biegnie POZA
blokiem ``sync_playwright()`` — synchroniczne API Playwrighta trzyma
uruchomioną pętlę asyncio i ORM Django odmówiłby pracy
(``SynchronousOnlyOperation``).
"""

import json
import logging
import re
import time
from dataclasses import dataclass, field
from importlib import import_module
from urllib.parse import parse_qs, quote, urlsplit

from django.conf import settings
from django.contrib.auth import BACKEND_SESSION_KEY, HASH_SESSION_KEY, SESSION_KEY
from django.core.exceptions import ImproperlyConfigured

from pbn_api.urls import CALLBACK_ALIASES

logger = logging.getLogger(__name__)

SCIEZKA_CALLBACKU = re.compile(
    r"^/pbn_api/(?:" + "|".join(map(re.escape, CALLBACK_ALIASES)) + r")/?$"
)

#: Wzorce URL dla CDP ``Fetch.enable``: powrót na callback (także gdy kod
#: przyjdzie POST-em, bez ``ott`` w adresie) oraz każdy adres niosący
#: ``ott=`` (gdyby PBN wracał na inną ścieżkę).
WZORCE_FETCH = ("*/pbn_api/*", "*ott=*")

LOKALNE_HOSTY = frozenset({"localhost", "127.0.0.1", "::1"})

STRONA_INFORMACYJNA = """<!doctype html><meta charset="utf-8">
<title>BPP: logowanie do PBN</title>
<body style="font-family: sans-serif; margin: 3em">
<h1>%s</h1><p>To okno można zamknąć — dalsze informacje są w terminalu.</p>
"""


@dataclass
class WynikPrzegladarki:
    """Co zobaczyła przeglądarka. Bez dostępu do bazy."""

    #: ``callback`` — lokalny BPP obsłużył callback; ``ott`` — mamy kod, ale
    #: nie przeszedł przez lokalny callback; ``callback_bez_ott``;
    #: ``niezalogowany``; ``zamknieto``; ``timeout``.
    status: str = "timeout"
    ott: str | None = None
    #: (metoda, url bez query) żądań zatrzymanych przed wyjściem do obcego
    #: hosta — do diagnostyki i testów.
    zatrzymane: list = field(default_factory=list)
    szczegoly: str = ""


def adres_jest_lokalny(base_url: str) -> bool:
    return (urlsplit(base_url).hostname or "") in LOKALNE_HOSTY


def utworz_sesje(user) -> tuple[str, str]:
    """Tworzy po stronie serwera sesję zalogowanego użytkownika.

    Zwraca ``(nazwa ciasteczka, wartość)``. Działa, bo ten proces i lokalny
    BPP współdzielą bazę i ``SECRET_KEY`` (oba z ``settings/local.py``).
    """
    sesja = import_module(settings.SESSION_ENGINE).SessionStore()
    sesja[SESSION_KEY] = str(user.pk)
    sesja[BACKEND_SESSION_KEY] = "django.contrib.auth.backends.ModelBackend"
    sesja[HASH_SESSION_KEY] = user.get_session_auth_hash()
    sesja.save()
    return settings.SESSION_COOKIE_NAME, sesja.session_key


def ott_z_zadania(zadanie: dict) -> str | None:
    """Kod OTT z zatrzymanego żądania CDP: z query albo z ciała POST."""
    w_query = parse_qs(urlsplit(zadanie["url"]).query).get("ott")
    if w_query and w_query[0]:
        return w_query[0]
    cialo = zadanie.get("postData") or ""
    if not cialo:
        return None
    w_formularzu = parse_qs(cialo).get("ott")
    if w_formularzu and w_formularzu[0]:
        return w_formularzu[0]
    try:
        dane = json.loads(cialo)
    except json.JSONDecodeError:
        return None  # ciało w innym formacie niż formularz/JSON — brak kodu
    if isinstance(dane, dict):
        wartosc = dane.get("ott") or dane.get("oneTimeToken")
        if isinstance(wartosc, str) and wartosc:
            return wartosc
    return None


class _Przechwytywacz:
    """Zatrzymuje powrót z PBN na obcy host i kieruje go na lokalny BPP."""

    def __init__(self, base_url, pbn_api_root, wynik):
        self.base_url = base_url.rstrip("/")
        self.lokalny_netloc = urlsplit(self.base_url).netloc
        self.pbn_netloc = urlsplit(pbn_api_root or "").netloc
        self.wynik = wynik
        self.callback_lokalny_obsluzony = False
        self._sesje = []

    def podepnij(self, context, page):
        cdp = context.new_cdp_session(page)
        cdp.on("Fetch.requestPaused", lambda ev: self._wstrzymane(cdp, ev))
        cdp.send(
            "Fetch.enable",
            {
                "patterns": [
                    {"urlPattern": wzorzec, "requestStage": "Request"}
                    for wzorzec in WZORCE_FETCH
                ]
            },
        )
        page.on("response", self._odpowiedz)
        self._sesje.append(cdp)

    def _odpowiedz(self, response):
        czesci = urlsplit(response.url)
        if czesci.netloc == self.lokalny_netloc and SCIEZKA_CALLBACKU.match(
            czesci.path
        ):
            self.callback_lokalny_obsluzony = True

    def _wstrzymane(self, cdp, ev):
        from playwright.sync_api import Error as BladPlaywrighta

        try:
            self._rozstrzygnij(cdp, ev)
        except BladPlaywrighta:
            # Żądanie zostaje wstrzymane (nie wychodzi z przeglądarki) — to
            # bezpieczna strona błędu. Logujemy, pętla główna dojdzie do
            # limitu czasu albo zobaczy zamknięte okno.
            logger.exception("PBN: błąd obsługi wstrzymanego żądania (CDP)")

    def _rozstrzygnij(self, cdp, ev):
        zadanie = ev["request"]
        czesci = urlsplit(zadanie["url"])
        ident = {"requestId": ev["requestId"]}

        if czesci.netloc == self.lokalny_netloc:
            cdp.send("Fetch.continueRequest", ident)
            return

        na_callback = bool(SCIEZKA_CALLBACKU.match(czesci.path))
        if czesci.netloc == self.pbn_netloc and not na_callback:
            # Wewnętrzne adresy PBN (mogą nieść ``ott=`` między jego stronami).
            cdp.send("Fetch.continueRequest", ident)
            return

        ott = ott_z_zadania(zadanie)
        if not na_callback and not ott:
            cdp.send("Fetch.continueRequest", ident)  # wzorzec trafił przypadkiem
            return

        # Od tego miejsca żądanie NIE wychodzi do obcego hosta.
        self.wynik.zatrzymane.append(
            (zadanie["method"], f"{czesci.scheme}://{czesci.netloc}{czesci.path}")
        )
        if ott:
            self.wynik.ott = ott

        if na_callback and ott:
            lokalnie = f"{self.base_url}{czesci.path}?ott={quote(ott, safe='')}"
            cdp.send(
                "Fetch.fulfillRequest",
                {
                    **ident,
                    # 303: także powrót POST-em kończy jako GET na lokalnym BPP.
                    "responseCode": 303,
                    "responseHeaders": [{"name": "Location", "value": lokalnie}],
                },
            )
            return

        if ott:
            self.wynik.status = "ott"
            naglowek = "Kod z PBN przechwycony"
        else:
            self.wynik.status = "callback_bez_ott"
            naglowek = "PBN wrócił bez kodu OTT w adresie"
        cdp.send(
            "Fetch.fulfillRequest",
            {
                **ident,
                "responseCode": 200,
                "responseHeaders": [
                    {"name": "Content-Type", "value": "text/html; charset=utf-8"}
                ],
                "body": _b64(STRONA_INFORMACYJNA % naglowek),
            },
        )


def _b64(tekst: str) -> str:
    import base64

    return base64.b64encode(tekst.encode()).decode()


def autoryzuj_w_przegladarce(
    context,
    base_url,
    ciasteczko,
    *,
    pbn_api_root="",
    limit_czasu=570,
    komunikat=print,
) -> WynikPrzegladarki:
    """Prowadzi przeglądarkę przez „autoryzuj PBN API" lokalnego BPP.

    ``context`` to ``BrowserContext`` Chromium. Funkcja nie dotyka bazy.
    Do PBN loguje się CZŁOWIEK — niczego tam nie wpisujemy.
    """
    from playwright.sync_api import Error as BladPlaywrighta

    base_url = base_url.rstrip("/")
    wynik = WynikPrzegladarki()
    przechwytywacz = _Przechwytywacz(base_url, pbn_api_root, wynik)

    nazwa, wartosc = ciasteczko
    context.add_cookies([{"name": nazwa, "value": wartosc, "url": base_url}])
    page = context.pages[0] if context.pages else context.new_page()
    przechwytywacz.podepnij(context, page)
    context.on("page", lambda nowa: przechwytywacz.podepnij(context, nowa))

    try:
        page.goto(f"{base_url}/pbn_api/authorize?next=/")
        if urlsplit(page.url).netloc == urlsplit(base_url).netloc:
            # Adres wpisany „z palca" (Sec-Fetch-Site: none) → strona pośrednia
            # z formularzem POST. Brak formularza = nie jesteśmy zalogowani.
            przycisk = page.locator(
                "form[action$='/pbn_api/authorize'] button[type=submit]"
            )
            if not przycisk.count():
                wynik.status = "niezalogowany"
                wynik.szczegoly = page.url
                return wynik
            przycisk.first.click()

        komunikat(
            "Zaloguj się w PBN w otwartym oknie przeglądarki "
            f"(czekam do {limit_czasu} s)…"
        )
        koniec = time.monotonic() + limit_czasu
        while time.monotonic() < koniec:
            if przechwytywacz.callback_lokalny_obsluzony:
                page.wait_for_load_state("load")
                wynik.status = "callback"
                return wynik
            if wynik.status in ("ott", "callback_bez_ott"):
                return wynik
            page.wait_for_timeout(200)
    except BladPlaywrighta as e:
        if page.is_closed() or "closed" in str(e).lower():
            wynik.status = "zamknieto"
            return wynik
        raise
    return wynik


def sprawdz_token(uczelnia, token) -> int:
    """Jedno lekkie, tylko-odczytowe zapytanie do PBN tokenem użytkownika.

    Zwraca liczbę publikacji w profilu instytucji. Wyjątki klienta PBN
    przepuszcza (wywołujący zamienia je na komunikat).
    """
    if not uczelnia.pbn_app_token:
        raise ImproperlyConfigured("Brak tokena aplikacji dla API PBN")
    return uczelnia.pbn_client(token).get_institution_publications(page_size=1).count()
