"""Routing ASGI: rozdział /mcp od reszty serwisu oraz obsługa lifespanu."""

from __future__ import annotations

import json
import logging
import time

import rollbar
from bpp_mcp.auth import set_current_bearer
from django.conf import settings
from django.db import Error as BladBazy
from redis.exceptions import ConnectionError as BladRedisa
from redis.exceptions import TimeoutError as PrzekroczonyCzasRedisa

from django_bpp.client_ip import get_client_ip
from mcp_server.auth import BramkaBearera
from mcp_server.kontekst import (
    DaneZadania,
    dane_zadania,
    domena_hosta,
    schemat_zadania,
)
from mcp_server.start import StartMcp
from mcp_server.uczelnia import host_rozstrzyga_uczelnie
from mcp_server.zdrowie import stan_startu

logger = logging.getLogger(__name__)

#: „Infrastruktura pod ``/mcp`` nie odpowiada" — JEDEN epizod, niezależnie od
#: tego, która warstwa go zauważyła. Trzy typy, nie jeden:
#:
#: * ``BladBazy`` (``django.db.Error``) — leżący PostgreSQL;
#: * ``BladRedisa`` (``redis.exceptions.ConnectionError``) — ``sites.site``
#:   i ``bpp.uczelnia`` są w ``CACHEOPS`` (``production.py``), a
#:   ``CACHEOPS_DEGRADE_ON_FAILURE`` nie jest ustawione, więc leżący Redis
#:   rzuca wyjątkiem Z SAMEGO ORM-u, nie z bazy;
#: * ``PrzekroczonyCzasRedisa`` (``redis.exceptions.TimeoutError``) — NIE jest
#:   podklasą ``ConnectionError`` (jego MRO to ``RedisError`` → ``Exception``,
#:   zweryfikowane w zainstalowanym pakiecie). WISZĄCY Redis daje więc inny typ
#:   niż Redis ODMAWIAJĄCY połączenia i bez tego wpisu leciałby do ogólnej
#:   siatki bezpieczeństwa w ``__call__``, która zgłasza BEZ rate-limitu —
#:   czyli dokładnie ten hałas raz-na-żądanie, który rate-limit ma wygaszać.
BLEDY_INFRASTRUKTURY = (BladBazy, BladRedisa, PrzekroczonyCzasRedisa)

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
        # Rate-limit zgłoszeń Rollbara przy awarii infrastruktury — JEDNA flaga
        # na OBIE bramki sięgające do bazy (uczelni i bearera), bo to JEDEN
        # epizod „infrastruktura nie odpowiada", a nie dwa. Patrz
        # ``_zglos_awarie_infrastruktury``.
        self._awaria_infrastruktury_zgloszona = False

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

        # `dane` wyliczamy DOPIERO wewnątrz siatki bezpieczeństwa (nie przed
        # `try` jak wcześniej) — usterka 2a z self-review PR #804:
        # `_dane(scope)` woła bez `errors=` na `.decode()`, więc niepoprawny
        # UTF-8 w nagłówku (np. `Authorization: Bearer \xff`) rzucał
        # `UnicodeDecodeError` PRZED jakimkolwiek `try`, co dawało gołe 500
        # bez wpisu w logu audytowym i bez Rollbara — anonimowo, jednym
        # żądaniem. Poprawka niżej (`errors="replace"`) usuwa tę KONKRETNĄ
        # przyczynę, ale `dane` zostaje w siatce jako obrona w głąb: kolejny
        # nieoczywisty błąd w tej funkcji też dostanie log + zgłoszenie
        # + kontrolowane 503, nie gołe 500.
        dane = None
        try:
            dane = self._dane(scope)
            if not domena_hosta(dane.host):
                # NAJPIERW poprawność samego nagłówka, PRZED bramką uczelni
                # i przed dotknięciem bazy. Powód w ``kontekst.domena_hosta``:
                # allowlista SDK przepuszcza ``host:<cokolwiek>``, bramka
                # uczelni obcinała port i widziała prawdziwy ``Site``, a
                # ``httpx.URL`` w kliencie wysypywał się dopiero na budowie
                # ``base_url`` — wyjątkiem, który wrapper narzędzi zgłaszał do
                # Rollbara. Kontrolowane 421 zamyka ten kanał, a jednocześnie
                # nie ujawnia, co serwis obsługuje (patrz ``_nieznany_host``).
                logger.warning(
                    "mcp: odrzucony niepoprawny nagłówek Host: %r", dane.host
                )
                await self._nieznany_host(sledzacy)
                return
            await self._obsluz(sciezka, scope, receive, sledzacy, dane, widziany)
        except Exception:
            # JEDNA siatka bezpieczeństwa na całą obsługę żądania — patrz
            # komentarz nad `except (BladBazy, BladRedisa)` w `_obsluz` o
            # tym, dlaczego TA gałąź nie duplikuje raportowania z węższych
            # except-ów: te kończą się (return) bez re-raise, więc do tego
            # miejsca dochodzi wyłącznie to, czego węższy except NIE złapał.
            logger.exception("mcp: nieobsłużony wyjątek w obsłudze żądania")
            rollbar.report_exc_info()
            if "status" not in widziany:
                # Nie próbuj wysyłać drugiego `http.response.start` — ASGI
                # nie pozwala na dwa starty odpowiedzi, a warstwa niżej może
                # już swój wysłać (np. gdzieś w środku strumieniowania).
                await self._niedostepny(sledzacy)
        finally:
            logger.info(
                "mcp %s %s host=%s bearer=%s status=%s czas=%.3fs",
                scope.get("method", "?"),
                sciezka,
                dane.host if dane is not None else "?",
                # OBECNOŚĆ, nigdy wartość — token w logu byłby poświadczeniem
                # leżącym w pliku, który wędruje do agregatora i backupów.
                "tak" if dane is not None and dane.bearer else "nie",
                widziany.get("status"),
                time.monotonic() - poczatek,
            )

    def _zglos_awarie_infrastruktury(self, komunikat: str) -> None:
        """Zgłoś awarię bazy/cache RAZ NA EPIZOD, nie raz na żądanie.

        Rate-limit jak w ``StartMcp._trzymaj`` (B3, komentarz tam) — baza może
        leżeć dłużej niż jedno żądanie, a bez ograniczenia zgłaszalibyśmy
        Rollbarowi raz na KAŻDE żądanie w oknie awarii, czyli dokładnie ten
        hałas, który B2 usunęło z narzędzi. W odróżnieniu od startu menedżera tu
        żądania NIE kończą się, więc flaga wraca do zera dopiero po żądaniu
        obsłużonym w CAŁOŚCI bez awarii infrastruktury (patrz ``else`` przy
        bramce bearera) — kolejny, ODRĘBNY epizod znów trafi do Rollbara.

        Dlaczego JEDNA flaga na obie bramki: „baza/Redis nie odpowiada" to jeden
        stan świata. Osobna flaga per bramka znaczyłaby, że ten sam epizod
        zgłasza się dwa razy, a w scenariuszu „leżąca baza + ŻYWY Redis"
        (cacheops przepuszcza bramkę uczelni z cache'u, więc awaria wychodzi
        dopiero przy weryfikacji bearera) flaga uczelni i tak by nie zadziałała.
        """
        if self._awaria_infrastruktury_zgloszona:
            return
        logger.exception(komunikat)
        rollbar.report_exc_info()
        self._awaria_infrastruktury_zgloszona = True

    async def _obsluz(
        self, sciezka, scope, receive, send, dane: DaneZadania, widziany: dict
    ):
        """Właściwa obsługa żądania do ``/mcp`` — bez warstwy logowania.

        ``widziany`` to ten sam słownik, który ``__call__`` wypełnia w
        ``sledzacy``: potrzebny tu, żeby awaria PO rozpoczęciu odpowiedzi nie
        próbowała wysłać drugiego ``http.response.start`` (ASGI na to nie
        pozwala).
        """
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
        except BLEDY_INFRASTRUKTURY:
            # Bez tego `except` awaria bazy/cache leciała poza aplikację ASGI
            # jako gołe 500 bez treści i bez zgłoszenia do Rollbara (middleware
            # Django nie jest na tej ścieżce) — wprost sprzeczne z B3, które
            # ten sam diff wprowadził dla `zapewnij()`. Celujemy w konkretne
            # typy (patrz `BLEDY_INFRASTRUKTURY`), NIE w gołe `Exception` — dla
            # drugiego mamy siatkę bezpieczeństwa w `__call__`, a tu szerszy
            # złap przykryłby błędy programistyczne w
            # `host_rozstrzyga_uczelnie` i pozbawił je jej raportowania
            # (patrz tamten `except Exception`, bez rate-limitu).
            self._zglos_awarie_infrastruktury("mcp: awaria bazy w bramce uczelni")
            await self._niedostepny(send)
            return
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
        except BLEDY_INFRASTRUKTURY:
            # Druga — obok bramki uczelni — warstwa sięgająca do bazy PRZED
            # aplikacją MCP: `BramkaBearera` → `auth.zweryfikuj_token`. Bez tego
            # `except` awaria na TEJ ścieżce leciała do ogólnej siatki
            # bezpieczeństwa w `__call__`, która zgłasza BEZ rate-limitu.
            #
            # Scenariusz, w którym to boli: leżąca baza + ŻYWY Redis. Bramka
            # uczelni przechodzi wtedy z cacheops (`sites.site` i `bpp.uczelnia`
            # są w `CACHEOPS`), więc jej rate-limitowany `except` w ogóle się
            # nie uruchamia, a KAŻDE żądanie z bearerem daje osobne zgłoszenie
            # z siatki. Siatka adresuje *wyjątek*, nie *hałas* — rate-limit
            # musi być tutaj.
            self._zglos_awarie_infrastruktury("mcp: awaria bazy w bramce bearera")
            if "status" not in widziany:
                # Aplikacja MCP mogła już zacząć odpowiadać (drugi
                # `http.response.start` jest w ASGI błędem) — patrz ta sama
                # ostrożność w siatce w `__call__`.
                await self._niedostepny(send)
        else:
            # Flaga wraca do zera dopiero tutaj, po żądaniu przeprowadzonym
            # przez OBIE bramki bez awarii. Reset zaraz po bramce uczelni
            # (jak było wcześniej) kasowałby rate-limit w scenariuszu „baza
            # leży, Redis żyje": każde kolejne żądanie najpierw resetowałoby
            # flagę na bramce uczelni (przechodzi z cache'u), a potem zgłaszało
            # awarię bearera — czyli znowu raz na żądanie.
            #
            # WARUNEK ``dane.bearer`` jest tu konieczny, nie kosmetyczny.
            # Żądanie ANONIMOWE na ``/mcp`` (publiczna bramka, ``wymagany=
            # False``) w ogóle nie woła ``zweryfikuj_token`` — ``BramkaBearera
            # .__call__`` przy braku nagłówka ``Authorization`` przechodzi
            # prosto do aplikacji, nie dotykając bazy. Jego powodzenie NIE
            # jest więc dowodem, że baza znów odpowiada. Bez tego warunku
            # ruch PRZEPLECIONY anon/bearer (dokładnie ten, który jest
            # publicznym ``/mcp`` w scenariuszu „leżąca baza + żywy Redis")
            # resetowałby flagę na każdym anonimowym żądaniu, a zaraz potem
            # ponownie zgłaszał awarię przy kolejnym żądaniu z bearerem —
            # czyli z powrotem „zgłoszenie na każde żądanie z bearerem",
            # dokładnie ten hałas, który rate-limit ma wygaszać.
            #
            # Bramki uczelni to NIE dotyczy (choć flaga jest jedna, wspólna
            # dla obu): ``host_rozstrzyga_uczelnie`` jest wołane dla KAŻDEGO
            # żądania, anonimowego i z bearerem, więc samo dojście do tego
            # miejsca (czyli przejście przez obie bramki bez wyjątku) już
            # dowodzi, że ta konkretna ścieżka do bazy działa. Warunek niżej
            # jest więc ostrożniejszy niż to konieczne dla bramki uczelni,
            # ale to nie szkodzi — dla ŻĄDANIA ANONIMOWEGO flaga po prostu
            # zostaje ustawiona o jedno żądanie dłużej, aż nadejdzie pierwsze
            # żądanie z bearerem, które potwierdzi odzyskanie OBU bramek.
            if dane.bearer:
                self._awaria_infrastruktury_zgloszona = False
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
        #
        # UWAGA 2 (usterka 2a z self-review PR #804): ``errors="replace"`` na
        # WARTOŚCI jest wymagane — nagłówek to dane od klienta, nie coś, czemu
        # ufamy jako poprawnemu UTF-8. Bez tego `curl -H 'Authorization:
        # Bearer \xff'` dawał `UnicodeDecodeError` tu, w miejscu wywoływanym
        # PRZED jakąkolwiek siatką bezpieczeństwa w `__call__` — anonimowo,
        # jednym żądaniem, bez wpisu w logu i bez Rollbara. Ten sam wybór
        # (`errors="replace"`) robi już `mcp_server.auth.BramkaBearera` —
        # jedno źródło prawdy dla obu miejsc.
        naglowki = {
            k.lower().decode(): v.decode(errors="replace")
            for k, v in scope.get("headers", [])
        }
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
