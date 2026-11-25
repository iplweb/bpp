"""Logowanie do PBN dla LOKALNEJ instancji BPP z przechwyceniem powrotu.

PBN po zalogowaniu odsyła przeglądarkę na adres zwrotny zapisany przy
aplikacji w PBN, czyli na serwer produkcyjny klienta
(``https://<serwer klienta>/pbn_api/callback?ott=<kod>``), a nie na
``localhost``. Tutaj otwieramy w przeglądarce (Playwright, Chromium) stronę
logowania aplikacji PBN WSKAZANEJ uczelni i zatrzymujemy ten jeden powrót,
ZANIM wyjdzie z przeglądarki. Przechwycony kod OTT wymienia na token komenda
``pbn_zaloguj_lokalnie`` — tą samą ścieżką co ``/pbn_api/callback``
(``pbn_api.autoryzacja.zapisz_token_z_ott``), jawnie dla tej uczelni.

Dlaczego nie przez lokalne ``/pbn_api/authorize`` → ``/pbn_api/callback``:
te widoki wybierają uczelnię po domenie żądania (``Site``). Pod
``localhost`` w instalacji z kilkoma uczelniami trafiają w pierwszą
z brzegu — logowanie szłoby przez aplikację PBN innej uczelni niż ta, dla
której token potem sprawdzamy. Adres logowania budujemy więc sami z pól
wskazanej uczelni; mechanizm wyboru uczelni na produkcji zostaje nietknięty.

⚠️ Przechwytywanie idzie przez CDP (domena ``Fetch``), a NIE przez
``context.route()`` Playwrighta. ``route()`` nie widzi kolejnych skoków
przekierowania (zmierzone: handler nie jest wołany, żądanie dociera do
obcego serwera), a powrót z PBN to właśnie przekierowanie 302 po wysłaniu
formularza logowania. Nie „upraszczaj" tego do ``route()`` — test e2e
(``test_logowanie_lokalne_e2e.py``) liczy żądania, które dotarły do
„obcego" serwera.

Funkcje z tego modułu nie dotykają bazy: synchroniczne API Playwrighta
trzyma uruchomioną pętlę asyncio i ORM Django odmówiłby pracy
(``SynchronousOnlyOperation``). Baza jest używana przed i po bloku
przeglądarki, w komendzie.
"""

import base64
import json
import logging
import re
import time
from dataclasses import dataclass, field
from urllib.parse import parse_qs, urlsplit

from django.core.exceptions import ImproperlyConfigured

from pbn_api.client import OAuthMixin
from pbn_api.urls import CALLBACK_ALIASES

logger = logging.getLogger(__name__)

SCIEZKA_CALLBACKU = re.compile(
    r"^/pbn_api/(?:" + "|".join(map(re.escape, CALLBACK_ALIASES)) + r")/?$"
)

#: Wzorce URL dla CDP ``Fetch.enable``: powrót na callback (także gdy kod
#: przyjdzie POST-em, bez ``ott`` w adresie) oraz każdy adres niosący
#: ``ott=`` (gdyby PBN wracał na inną ścieżkę).
WZORCE_FETCH = ("*/pbn_api/*", "*ott=*")

STRONA_INFORMACYJNA = """<!doctype html><meta charset="utf-8">
<title>BPP: logowanie do PBN</title>
<body style="font-family: sans-serif; margin: 3em">
<h1>%s</h1><p>To okno zaraz się zamknie — dalsze informacje są w terminalu.</p>
"""


@dataclass
class WynikPrzegladarki:
    """Co zobaczyła przeglądarka. Bez dostępu do bazy."""

    #: ``ott`` — mamy kod; ``callback_bez_ott`` — PBN wrócił bez kodu;
    #: ``zamknieto`` — okno zamknięte; ``timeout``.
    status: str = "timeout"
    ott: str | None = None
    #: (metoda, url bez query) żądań zatrzymanych przed wyjściem do obcego
    #: hosta — do diagnostyki i testów.
    zatrzymane: list = field(default_factory=list)


def adres_logowania(uczelnia) -> str:
    """Strona logowania aplikacji PBN TEJ uczelni (ten sam adres, na który
    przekierowuje ``/pbn_api/authorize``)."""
    return OAuthMixin.get_auth_url(
        uczelnia.pbn_api_root.rstrip("/"), uczelnia.pbn_app_name
    )


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
    """Zatrzymuje powrót z PBN (na dowolny host poza samym PBN)."""

    def __init__(self, pbn_api_root, wynik):
        self.pbn_netloc = urlsplit(pbn_api_root or "").netloc
        self.wynik = wynik

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

        na_callback = bool(SCIEZKA_CALLBACKU.match(czesci.path))
        if czesci.netloc == self.pbn_netloc and not na_callback:
            # Wewnętrzne adresy PBN (mogą nieść ``ott=`` między jego stronami).
            cdp.send("Fetch.continueRequest", ident)
            return

        ott = ott_z_zadania(zadanie)
        if not na_callback and not ott:
            cdp.send("Fetch.continueRequest", ident)  # wzorzec trafił przypadkiem
            return

        # Od tego miejsca żądanie NIE wychodzi z przeglądarki.
        self.wynik.zatrzymane.append(
            (zadanie["method"], f"{czesci.scheme}://{czesci.netloc}{czesci.path}")
        )
        if ott:
            self.wynik.ott = ott
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
                "body": base64.b64encode(
                    (STRONA_INFORMACYJNA % naglowek).encode()
                ).decode(),
            },
        )


def przechwyc_ott(
    context, adres, *, pbn_api_root="", limit_czasu=900, komunikat=print
) -> WynikPrzegladarki:
    """Otwiera stronę logowania PBN i czeka na powrót z kodem OTT.

    ``context`` to ``BrowserContext`` Chromium. Do PBN loguje się CZŁOWIEK —
    niczego tam nie wpisujemy.
    """
    from playwright.sync_api import Error as BladPlaywrighta

    wynik = WynikPrzegladarki()
    przechwytywacz = _Przechwytywacz(pbn_api_root, wynik)

    page = context.pages[0] if context.pages else context.new_page()
    przechwytywacz.podepnij(context, page)
    context.on("page", lambda nowa: przechwytywacz.podepnij(context, nowa))

    try:
        page.goto(adres)
        komunikat(
            "Zaloguj się w PBN w otwartym oknie przeglądarki "
            f"(czekam do {limit_czasu} s)…"
        )
        koniec = time.monotonic() + limit_czasu
        while time.monotonic() < koniec:
            if wynik.status in ("ott", "callback_bez_ott"):
                return wynik
            page.wait_for_timeout(200)
    except BladPlaywrighta as e:
        if wynik.status in ("ott", "callback_bez_ott"):
            # Nawigacja przerwana naszą stroną informacyjną — kod już mamy.
            return wynik
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
