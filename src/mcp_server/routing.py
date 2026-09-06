"""Routing ASGI: rozdział /mcp od reszty serwisu oraz obsługa lifespanu."""

from __future__ import annotations

import json
import logging
import time

import rollbar
from bpp_mcp.auth import set_current_bearer
from django.conf import settings
from django.db import Error as BladBazy

from django_bpp.client_ip import get_client_ip
from mcp_server.auth import BramkaBearera
from mcp_server.kontekst import DaneZadania, dane_zadania, schemat_zadania
from mcp_server.start import StartMcp
from mcp_server.uczelnia import host_rozstrzyga_uczelnie
from mcp_server.zdrowie import stan_startu

logger = logging.getLogger(__name__)

#: Budżet czasu jednego wywołania narzędzia (spec D11).
BUDZET_SEKUND = getattr(settings, "MCP_BUDZET_SEKUND", 25.0)

SCIEZKA_PUBLICZNA = "/mcp"
SCIEZKA_Z_LOGOWANIEM = "/mcp/auth"
#: Sonda stanu MCP — patrz ``mcp_server.zdrowie`` (dlaczego nie ``/health/``).
SCIEZKA_STANU = "/mcp/status"


class LifespanMcp:
    """Obsługuje scope ``lifespan``, którego ProtocolTypeRouter nie zna.

    Klucza ``"lifespan"`` po prostu nie ma dziś w mapie routera, więc uvicorn
    dostaje ValueError, loguje „lifespan appears unsupported" i jedzie dalej —
    a menedżer sesji MCP nigdy nie wstaje (spec §2.4).
    """

    def __init__(self, start: StartMcp) -> None:
        self._start = start

    async def __call__(self, scope, receive, send):
        while True:
            komunikat = await receive()
            if komunikat["type"] == "lifespan.startup":
                try:
                    await self._start.zapewnij()
                except Exception as exc:
                    # Świadomie NIE połykamy: pod gunicornem worker padnie
                    # i zostanie respawnowany, czyli awaria będzie widoczna
                    # jako boot-loop, a nie jako cisza (spec §5.1).
                    await send({"type": "lifespan.startup.failed", "message": str(exc)})
                    return
                await send({"type": "lifespan.startup.complete"})
            elif komunikat["type"] == "lifespan.shutdown":
                await send({"type": "lifespan.shutdown.complete"})
                return


class RouterHttp:
    """Kieruje ``/mcp`` i ``/mcp/auth`` do MCP, resztę do Django."""

    def __init__(self, mcp_app, django_app, start: StartMcp) -> None:
        self._django = django_app
        self._start = start
        self._publiczny = BramkaBearera(mcp_app, wymagany=False)
        self._z_logowaniem = BramkaBearera(mcp_app, wymagany=True)
        # Rate-limit zgłoszeń Rollbara przy awarii bazy w bramce uczelni
        # (patrz ``_obsluz``) — patrz komentarz tam, dlaczego per instancję.
        self._blad_bazy_uczelni_zgloszony = False

    async def __call__(self, scope, receive, send):
        sciezka = scope.get("path", "")
        if sciezka == SCIEZKA_STANU:
            await self._stan(send)
            return
        if sciezka not in (SCIEZKA_PUBLICZNA, SCIEZKA_Z_LOGOWANIEM):
            await self._django(scope, receive, send)
            return

        if scope.get("method") == "GET" and self._chce_html(scope):
            await self._przekieruj(send, "/mcp/")
            return

        dane = self._dane(scope)
        poczatek = time.monotonic()
        # Kod odpowiedzi znamy dopiero z komunikatu wysłanego przez warstwę
        # niżej — podglądamy go w drodze na zewnątrz, żeby log audytowy
        # (spec §7.5) miał co zapisać. Żądania wewnętrzne nie trafiają ani do
        # access-logu nginksa, ani uvicorna, więc bez tego /mcp nie zostawia
        # ŻADNEGO śladu.
        widziany = {}

        async def sledzacy(komunikat):
            if komunikat["type"] == "http.response.start":
                widziany["status"] = komunikat["status"]
            await send(komunikat)

        try:
            await self._obsluz(sciezka, scope, receive, sledzacy, dane)
        finally:
            logger.info(
                "mcp %s %s host=%s bearer=%s status=%s czas=%.3fs",
                scope.get("method", "?"),
                sciezka,
                dane.host,
                # OBECNOŚĆ, nigdy wartość — token w logu byłby poświadczeniem
                # leżącym w pliku, który wędruje do agregatora i backupów.
                "tak" if dane.bearer else "nie",
                widziany.get("status"),
                time.monotonic() - poczatek,
            )

    async def _obsluz(self, sciezka, scope, receive, send, dane: DaneZadania):
        """Właściwa obsługa żądania do ``/mcp`` — bez warstwy logowania."""
        # PIERWSZA instrukcja i POZA jakimkolwiek cancel scope'em (spec §5.1).
        try:
            await self._start.zapewnij()
        except Exception:
            # KOLEJNOŚĆ MA ZNACZENIE: ``zapewnij()`` rzuca, gdy menedżer jest
            # zatruty, więc sprawdzenie ``self._start.zywy`` poniżej samo
            # z siebie nigdy by do tego stanu nie doszło — gałąź 503 byłaby
            # martwym kodem, a wyjątek wyszedłby poza aplikację ASGI jako gołe
            # 500 bez treści. Do Rollbara ta awaria trafia raz, ze ``StartMcp``
            # (patrz ``start._trzymaj``), a nie raz na żądanie.
            logger.exception("mcp: menedżer sesji MCP niedostępny")
            await self._niedostepny(send)
            return
        if not self._start.zywy:
            await self._niedostepny(send)
            return

        # Fail-closed na tożsamości uczelni (spec §7.2) — patrz
        # ``mcp_server.uczelnia``: host, dla którego nie da się rozstrzygnąć
        # uczelni, otwierałby bramkę API na oścież.
        try:
            rozstrzygnieta = await host_rozstrzyga_uczelnie(dane.host)
        except BladBazy:
            # Bez tego `except` awaria bazy leciała poza aplikację ASGI jako
            # gołe 500 bez treści i bez zgłoszenia do Rollbara (middleware
            # Django nie jest na tej ścieżce) — wprost sprzeczne z B3, które
            # ten sam diff wprowadził dla `zapewnij()`. Celujemy w
            # `django.db.Error`, NIE w gołe `Exception`: szerszy złap
            # przykryłby też błędy programistyczne w `host_rozstrzyga_uczelnie`.
            #
            # Rate-limit jak w `StartMcp._trzymaj` (B3, komentarz tam) —
            # baza może leżeć dłużej niż jedno żądanie, a bez ograniczenia
            # zgłaszalibyśmy Rollbarowi raz na KAŻDE żądanie w oknie awarii,
            # czyli dokładnie ten hałas, który B2 usunęło z narzędzi. W
            # odróżnieniu od startu menedżera, tu żądania NIE kończą się —
            # więc zgłaszamy raz na epizod i resetujemy przy najbliższym
            # powodzeniu, żeby kolejna, odrębna awaria też trafiła do
            # Rollbara.
            if not self._blad_bazy_uczelni_zgloszony:
                logger.exception("mcp: awaria bazy w bramce uczelni")
                rollbar.report_exc_info()
                self._blad_bazy_uczelni_zgloszony = True
            await self._niedostepny(send)
            return
        self._blad_bazy_uczelni_zgloszony = False
        if not rozstrzygnieta:
            logger.warning(
                "mcp: odrzucony host bez jednoznacznej uczelni: %r", dane.host
            )
            await self._nieznany_host(send)
            return

        zeton = dane_zadania.set(dane)
        # DWA ContextVary, nie jeden. `BppClient._auth_kwargs` czyta token
        # z WŁASNEGO ContextVara pakietu bpp_mcp (`bpp_mcp.auth`), nie
        # z naszego. Bez tej linii `DaneZadania.bearer` nie ma żadnej drogi
        # do żądania wychodzącego i KAŻDE wywołanie leci anonimowo — czyli
        # zalogowany użytkownik po cichu traci dostęp do swoich danych,
        # a cała warstwa OAuth staje się dekoracją.
        set_current_bearer(dane.bearer)
        try:
            if sciezka == SCIEZKA_Z_LOGOWANIEM:
                # SDK montuje trasę jako Route (^/mcp$), nie Mount — bez
                # przepisania drugi adres dostałby 404 (spec §5.1, BL-1).
                scope = dict(scope, path=SCIEZKA_PUBLICZNA, raw_path=b"/mcp")
                await self._z_logowaniem(scope, receive, send)
            else:
                await self._publiczny(scope, receive, send)
        finally:
            dane_zadania.reset(zeton)
            # set_current_bearer nie zwraca tokenu resetu, więc czyścimy
            # jawnie — inaczej token wyciekłby do następnego żądania
            # obsłużonego w tym samym kontekście.
            set_current_bearer(None)

    async def _stan(self, send) -> None:
        """Sonda ``/mcp/status``: bez uwierzytelnienia, bez bazy, bez Django.

        Startuje menedżera, jeśli jeszcze nie działa — pod Daphne (brak
        protokołu lifespan) start jest leniwy, więc sonda, która by go nie
        wyzwoliła, raportowałaby „padnięte” na zdrowym, świeżym workerze.
        Po pierwszym razie wywołanie jest idempotentne i nic nie kosztuje.
        """
        try:
            await self._start.zapewnij()
        except Exception:
            # To JEST odpowiedź tej sondy, a nie sytuacja wyjątkowa — do
            # Rollbara awaria poszła już ze ``StartMcp``. Logujemy z pełnym
            # traceback i odpowiadamy 503 poniżej.
            logger.exception("mcp/status: menedżer sesji MCP niedostępny")
        tresc, kod = stan_startu(self._start)
        await self._json(send, kod, tresc)

    @staticmethod
    def _chce_html(scope) -> bool:
        for klucz, wartosc in scope.get("headers", []):
            if klucz.lower() == b"accept" and b"text/html" in wartosc.lower():
                return True
        return False

    @staticmethod
    def _dane(scope) -> DaneZadania:
        # UWAGA: klucze ASGI to bajty — bez ``.decode()`` na kluczu każde
        # `naglowki.get("host", …)` z napisowym kluczem chybia (bajty != str)
        # i ZAWSZE trafia w wartość domyślną. Skutek po cichu: bearer
        # zawsze None, host zawsze "localhost" — mostek z pkt 2 briefu
        # wygląda podłączony, a nic nie przenosi.
        naglowki = {k.lower().decode(): v.decode() for k, v in scope.get("headers", [])}
        host = naglowki.get("host", "localhost")
        # nginx→uvicorn jest plaintext; prawdziwy schemat niesie nagłówek
        # wskazany przez SECURE_PROXY_SSL_HEADER (spec §7.6). Nagłówka NIE
        # przekazujemy dalej — służy wyłącznie do zbudowania adresu bazowego.
        scheme = schemat_zadania(naglowki, scope.get("scheme", "http"))
        bearer = None
        surowy = naglowki.get("authorization", "")
        if surowy.lower().startswith("bearer "):
            bearer = surowy.split(" ", 1)[1].strip()
        return DaneZadania(
            host=host,
            scheme=scheme,
            ip=get_client_ip(_UdajeRequest(scope, naglowki)),
            bearer=bearer,
            deadline=time.monotonic() + BUDZET_SEKUND,
        )

    @staticmethod
    async def _przekieruj(send, gdzie: str) -> None:
        await send(
            {
                "type": "http.response.start",
                "status": 307,
                "headers": [(b"location", gdzie.encode())],
            }
        )
        await send({"type": "http.response.body", "body": b""})

    @classmethod
    async def _niedostepny(cls, send) -> None:
        await cls._json(send, 503, {"error": "mcp_unavailable"})

    @classmethod
    async def _nieznany_host(cls, send) -> None:
        """421 Misdirected Request — ten sam kod, którym SDK odrzuca zły Host.

        Treść celowo nie zdradza, których hostów serwis obsługuje: to jest
        odpowiedź dla nieuwierzytelnionego świata.
        """
        await cls._json(send, 421, {"error": "unknown_host"})

    @staticmethod
    async def _json(send, kod: int, tresc: dict) -> None:
        cialo = json.dumps(tresc).encode()
        await send(
            {
                "type": "http.response.start",
                "status": kod,
                "headers": [
                    (b"content-type", b"application/json"),
                    (b"content-length", str(len(cialo)).encode()),
                ],
            }
        )
        await send({"type": "http.response.body", "body": cialo})


class _UdajeRequest:
    """Minimalny obiekt zgodny z tym, czego oczekuje ``get_client_ip``."""

    def __init__(self, scope, naglowki):
        klient = scope.get("client") or ("", 0)
        self.META = {"REMOTE_ADDR": klient[0]}
        xff = naglowki.get("x-forwarded-for")
        if xff:
            self.META["HTTP_X_FORWARDED_FOR"] = xff
