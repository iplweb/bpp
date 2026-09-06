# Hostowany serwer MCP w serwisie BPP (`/mcp`) — projekt 1 z 3

Data: 2026-09-05 (wersja 4, 2026-09-06)
Status: projekt do zatwierdzenia
Poprzednik: `2026-07-11-mcp-oauth-authorization-design.md` (warstwa OAuth po
stronie BPP — **zrealizowana**, `src/oauth_mcp/`)

> **Historia dokumentu.** Wersja 1: „wymaga przeprojektowania". Wersja 2:
> „niewdrażalne — trzy blokery" (B1–B3). Wersja 3 zamknęła B1, ale wprowadziła
> trzy nowe blokery we własnych rozwiązaniach B2/B3 (BL-1…BL-3). Ta wersja
> zamyka BL-1…BL-3 i jedenaście poprawek. Rozliczenie w §14.

---

## 1. Cel i motywacja

Dostęp AI do danych BPP idzie dziś przez `bpp-mcp` — pakiet z PyPI instalowany
do klienta MCP jako serwer stdio. Trzy koszty:

1. **Próg wejścia.** Potrzebny Python i `uvx`, a przede wszystkim użytkownik
   musi **znać i wpisać adres swojej instancji** (`BPP_BASE_URL` celowo bez
   wartości domyślnej — każde wdrożenie to inna uczelnia).
2. **Odcięta kategoria klientów.** Klienci webowi (claude.ai) i urządzenia
   mobilne **nie mają jak uruchomić procesu lokalnego**.
3. **Skos wersji.** N wersji pakietu × M wdrożeń BPP.

**Cel:** BPP wystawia własny endpoint MCP, wyjeżdżający z tym samym obrazem
dockerowym co reszta serwisu. Użytkownik wkleja adres swojej instancji
z dopiskiem `/mcp` i to jest cała konfiguracja.

### 1.1 Zasięg — uczciwie

Wersja 1 obiecywała „claude.ai, ChatGPT, Cursor, VS Code". **To była
nieprawda.** Allowlista redirect_uri w DCR (`src/oauth_mcp/views_dcr.py:16-22`)
dopuszcza wyłącznie `claude.ai`, `*.claude.ai`, `claude.com`, `localhost`
i `127.0.0.1`. ChatGPT i Cursor **nie zarejestrują klienta**.

Realny zasięg **logowania** to ekosystem Claude. **Dostęp anonimowy nie wymaga
DCR w ogóle**, więc publiczna część działa z każdym klientem obsługującym
zdalne MCP. Rozszerzenie allowlisty jest osobną decyzją bezpieczeństwa (§13).

---

## 2. Kontekst — ustalenia z kodu i z probe'ów

Numery linii wg `dev` @ `31d3d4612`. **[probe]** = ustalenie z uruchomionego
kodu, nie z lektury.

### 2.1 Warstwa OAuth po stronie BPP — istnieje i jest kompletna

| Element | Plik |
|---|---|
| `/o/authorize/`, `/o/token/`, `/o/revoke_token/` | `oauth_mcp/urls.py` |
| DCR `/o/register/` (RFC 7591) + allowlista + rate-limit | `oauth_mcp/views_dcr.py:16-22` |
| AS metadata RFC 8414 | `oauth_mcp/views_metadata.py` |
| `StrictOAuth2Authentication` — bearer → `request.user`, twarde 401 | `oauth_mcp/authentication.py` |
| `ApiReadOnlyForBearerMiddleware` — mutacje bearerem → 403 | `oauth_mcp/middleware.py:33` |
| `WhoAmIView` — routing w `api_v1/urls.py:265`, pod `z_bramka_api_v1` | `oauth_mcp/views_whoami.py` |
| revoke przy zmianie hasła / dezaktywacji | `oauth_mcp/signals.py` |

Kolejność w `DEFAULT_AUTHENTICATION_CLASSES` (`base.py:1057-1059`):
`StrictOAuth2Authentication`, `SessionAuthentication`, `BasicAuthentication`.

### 2.2 Pakiet `bpp-mcp` 0.4.0

Wydany (projekt 2, PR-y #21–#23). Wystawia `register_tools(mcp)` (**11 narzędzi
+ 1 prompt**, `server.py:315-330`), `KontekstApp`, `BppClient(transport=...)`,
`TrybAuth.W_PROCESIE`, `BppClient._slownik_cache()`.

**Ograniczenie, które kształtuje ten projekt:** `BppClient.__init__` zapamiętuje
`self._api_root = config.api_root` **raz** (`client.py:135`), `Config` jest
`frozen` (`config.py:25`), a `_full_url` czyta zapamiętaną wartość
(`client.py:186`). Nie ma szwu na host per żądanie. Stąd D9 (§5.3).

Kontrakt `register_tools` mówi „`KontekstApp` **albo obiekt o tych samych
atrybutach**" (`server.py:291-315`) — i to jest furtka, z której korzystamy.

### 2.3 MCP SDK 2.0

- **[probe]** `stateless_http` i `json_response` są parametrami
  `streamable_http_app()` (`mcpserver/server.py:1218-1229`), **nie**
  konstruktora.
- **[probe]** `POST /mcp` bez wejścia w lifespan →
  `RuntimeError: Task group is not initialized` (`streamable_http_manager.py:174`),
  także przy `stateless_http=True`. Po wejściu — **200** i poprawny `initialize`.
- **[probe]** Aplikacja MCP ma **własną allowlistę hostów**
  (`TransportSecuritySettings`), niezależną od `ALLOWED_HOSTS`. Nieznany
  `Host` → **421**.
- Semantyka tej allowlisty **różni się od Django**: dopasowanie dokładne albo
  wzorzec `host:*` (`transport_security.py:49-60`). Django-owe `.domena` i `*`
  **nie działają**. Sprawdzany jest też `Origin` (`:65-70`).
- Przekazanie `host=` **bez** `transport_security` po cichu **wyłącza** ochronę
  (`lowlevel/server.py:738-744`).
- `RequireAuthMiddleware` owija trasę **wyłącznie** gdy podano `token_verifier`
  (`lowlevel/server.py:793-806`) — i wtedy odrzuca 401-ką **każde** żądanie bez
  tożsamości (`bearer_auth.py:93-97`). Czyli SDK nie zna trybu „anonim
  dozwolony, zły token odrzucony". Stąd D10 (§5.4).
- `SessionMessage.metadata.request` niesie do narzędzia **cały obiekt
  `Request` zewnętrznego żądania** (`streamable_http.py:608-611`), z `Cookie`
  włącznie. Dziś czyta z niego tylko `bearer_from_request` (`bpp_mcp/auth.py:46-53`),
  ale D6 stoi przez to na **dyscyplinie kodu w `bpp-mcp`**, nie na izolacji
  transportowej (§7.1).
- SDK zamienia każdy wyjątek narzędzia na `CallToolResult(is_error=True)`
  (`mcpserver/server.py:423-424`) — wyjątki narzędzi **nie docierają** do
  warstwy ASGI (§7.5).
- Dwie ścieżki protokołu mają **różny model czasu życia**: „modern"
  (`MCP-Protocol-Version` spoza `HANDSHAKE_PROTOCOL_VERSIONS`, `manager:183-187`)
  wykonuje handler w zadaniu żądania, „legacy" — w zadaniu grupy menedżera.
  Budżet czasu musi działać w obu (§5.2).
- Czy `stateless_http=True` + `GET` daje 405, **nie zostało potwierdzone** —
  wersja 3 cytowała `streamable_http.py:788-790,848`, ale 788-790 dotyczy
  DELETE, a 848 to generyczna obsługa nieobsługiwanej metody. Do sprawdzenia
  empirycznego, zanim powstanie test (§11).
- Lifespan wchodzi **raz na serwer**; `session_manager.run()` można wejść
  **raz na instancję** (`streamable_http_manager.py:137-143`).

### 2.4 Serwery ASGI — trzy różne, nie jeden

To jest źródło blokera B2.

| Środowisko | Serwer | Lifespan |
|---|---|---|
| produkcja | `gunicorn` + `UvicornWorker` (`entrypoint-appserver.sh:104`) | **tak** |
| kontener dev | `uvicorn --reload` (`:94`) | **tak** |
| **lokalnie: `run-site run` → `manage.py runserver`** | **Daphne** (`daphne` w `INSTALLED_APPS`, `base.py:391`) | **NIE** |
| **testy Playwright: `channels_live_server`** | **Daphne** (`src/channels_live_server.py:11,22`) | **NIE** |

W źródłach `daphne` **nie ma ani jednego wystąpienia słowa `lifespan`**.

`ProtocolTypeRouter` to piętnaście linii (`channels/routing.py:45-52`): lookup
w słowniku, a dla typu spoza słownika `raise ValueError` (linie 50-52). Klucza
`"lifespan"` po prostu nie ma, więc uvicorn dostaje `ValueError`, loguje
„lifespan appears unsupported" (`lifespan/on.py:88-93`) i jedzie dalej — błąd
jest cichy. **To nie jest ograniczenie channels, tylko brakujący wpis
w naszej konfiguracji.**

Pozostała infrastruktura:

- `max_requests=1000` + jitter 200 w `docker/appserver/gunicorn_conf.py:44-45`;
  gunicornowy `timeout` to heartbeat, **nie** limit czasu żądania (`:47-51`).
- nginx: `Host $host`, `X-Forwarded-For`, `X-Forwarded-Proto`
  (`_bpp-locations.conf:129-134`), `proxy_read_timeout 300s` (`:140`), trzy
  strefy `limit_req` (`:74-89`) — `/api/` 60 r/s, `/admin/` 50 r/s, `/` 100 r/s.
- **ModSecurity/CRS**; jedyne wyłączenie dla DjangoQL to
  `^/(bpp|api/v1)/zapytanie/` (`modsecurity-override.conf.template:79`).
- nginx→uvicorn jest **plaintext**; HTTPS Django rozpoznaje z
  `X-Forwarded-Proto` (`production.py:161`), a `SECURE_SSL_REDIRECT=True`
  (`:168`).

### 2.5 Bramka API i model tożsamości hosta

Kolejność w `BramkaApiV1` (`src/api_v1/permissions.py:66-68`), cytat
z docstringu:

> 1. uczelnia nierozstrzygnięta (pusta baza, kreator konfiguracji, brak
>    mapowania Site→Uczelnia) → **przepuszczamy**, bo nie ma kto podjąć decyzji

`Uczelnia` rozstrzyga się z nagłówka `Host` (`SiteResolutionMiddleware`,
`Uczelnia.objects.get_for_request`).

**Zakres zagrożenia — sprostowanie wobec wersji 3.** Nie jest tak, że nieznany
host zawsze daje `Uczelnia=None`: `_site_dla_requestu` spada na `SITE_ID`
(`uczelnia.py:97-104`), a `uczelnia_dla_site` na „jedyną-albo-None"
(`:126-129`). W instalacji **jednouczelnianej** nieznany host trafi więc na
właściwą uczelnię. Obejście bramki zachodzi w instalacji **wielouczelnianej**
(>1 `Uczelnia`) albo bez `SITE_ID`.

Tam jednak skutek jest dokładnie taki, jak opisano: `BramkaApiV1` przepuszcza
bezwarunkowo, omijając wszystkie sześć przełączników, a
`UkryjStatusyKorektyMixin.ukryte_statusy` daje `None`
(`viewsets/common.py:9-13`) → rekordy ukrytych statusów przestają być
filtrowane. D5 zostaje bez zmian — po prostu uzasadnienie dotyczy
wielouczelnianości, nie każdego wdrożenia.

`SearchAnonThrottle` dziedziczy po `AnonRateThrottle`. Bez `NUM_PROXIES`
(nie ma go w settings) DRF kluczuje po **całym** `X-Forwarded-For`, gdy jest
obecny (`rest_framework/throttling.py:29-39`); bez XFF — po `REMOTE_ADDR`,
czyli po `scope["client"]`.

`get_client_ip` bierze **skrajnie prawy** XFF (`django_bpp/client_ip.py:33-36`).

---

## 3. Trzy projekty, nie jeden

| # | Projekt | Status |
|---|---|---|
| 1 | **Hosting MCP w BPP** — routing ASGI, klient w procesie, auth, strona | **ten spec** |
| 2 | Szwy w `bpp-mcp` | **zrobione** — 0.4.0 na PyPI |
| 3 | Konsolidacja reguł tokenu w `oauth_mcp/tokens.py` | osobny spec, §13 |

Projekt 3 wypada świadomie: to zmiana w **testowanej warstwie
uwierzytelniania**, a wrzucanie jej do środka feature'a było błędem.

---

## 4. Decyzje architektoniczne

| # | Decyzja | Uzasadnienie |
|---|---|---|
| D1 | Narzędzia z `bpp-mcp`, zero kopii w `src/` | jedna implementacja |
| D2 | Klucz `"lifespan"` w istniejącym `ProtocolTypeRouter` **+ leniwy start w osobnym zadaniu** | klucz naprawia uvicorna; leniwy start naprawia Daphne; osobne zadanie jest warunkiem poprawności, nie optymalizacją (§2.4, §5.1) |
| D3 | `stateless_http=True` + `json_response=True` | recykling workera zabiłby sesję stateful; `json_response` znosi SSE |
| D4 | Dane przez `httpx.ASGITransport` na `django_asgi_app` | ta sama ścieżka kodu, bez gniazda |
| D5 | Wewnętrzne żądanie dziedziczy `Host`, scheme i IP klienta | inaczej `Uczelnia=None` → obejście bramki i wyciek (§7.2) |
| D6 | Przekazujemy **wyłącznie `Bearer`** | inaczej Basic i sesja omijają model OAuth (§7.1) |
| D7 | Polityka dostępu dziedziczona z `/api/v1/` | anonim czyta publiczne, bearer odblokowuje resztę |
| D8 | Read-only | narzędzia wykonują wyłącznie GET |
| **D9** | **`BppClient` per żądanie**, przez property w obiekcie lifespanu | `_api_root` zapamiętany w `__init__` (§2.2); rozwiązuje też cache i semafor |
| **D10** | **Dwa adresy: `/mcp` (publiczny) i `/mcp/auth` (zawsze 401 bez tokenu)**, z przepisaniem ścieżki | SDK montuje `Route`, nie `Mount`, więc drugi adres wymaga przepisania (§5.1); SDK nie zna trybu „anonim tak, zły token nie" (§2.3); dwa adresy usuwają zależność od nieznanego zachowania klientów |
| **D11** | **Jawny sufit czasu i współbieżności — egzekwowany w `BppClientInProcess`** | timeouty `httpx` martwe przy `ASGITransport`, gunicornowy `timeout` to heartbeat (§2.4) |
| **D12** | `follow_redirects=False` w kliencie w procesie | inaczej `SECURE_SSL_REDIRECT` po cichu podwaja każde żądanie, a kreator instalacji przekierowuje na HTML (§7.6) |

---

## 5. Architektura

```
              gunicorn+uvicorn (prod) | Daphne (dev, testy)
                             │
               django_bpp.asgi:application  =  ProtocolTypeRouter
                             │            (ten sam co dziś, +1 klucz)
        ┌────────────────────┼────────────────────┐
   "lifespan"            "http"              "websocket"
        │                    │                     │
   LifespanMcp          RouterHttp          AllowedHostsOriginValidator
   (nowy)               (nowy)              + AuthMiddlewareStack
        │              ┌─────┴─────┐        + URLRouter
        │        /mcp*         reszta       ── BEZ ZMIAN ──
        │              │           │
        │        BramkaBearera     │   ← 401 + WWW-Authenticate (§5.4)
        │              │           │
        │        KontekstMcp       │   ← host/scheme/IP/limity → ContextVar
        │              │           │
        └── start ──→ aplikacja MCP│
                      │            │
                 register_tools    │
                      │            │
              BppClient (per żądanie, D9)
                      │            │
              ASGITransport        │
                      │            │
              KlientScope ─────────┤   ← nadpisuje scope["client"] (§5.2)
                      │            │
                      └──→  django_asgi_app  ←┘
```

### 5.1 Lifespan — dopisany klucz plus leniwy start

**Klucz.** `ProtocolTypeRouter` nie odrzuca lifespanu; odrzuca to, czego nie ma
w słowniku (§2.4). Dopisujemy:

```python
application = ProtocolTypeRouter(
    {
        "http": RouterHttp(mcp_app, django_asgi_app),
        "websocket": AllowedHostsOriginValidator(          # BEZ ZMIAN
            AuthMiddlewareStack(URLRouter(websocket_urlpatterns))
        ),
        "lifespan": LifespanMcp(mcp_app),                  # ← nowy klucz
    }
)
```

**Świadomie NIE zastępujemy routera własnym dyspozytorem** — przepisanie
brałoby na nas odtworzenie gałęzi websocketowej wraz z
`AllowedHostsOriginValidator` i `AuthMiddlewareStack`, czyli ruszanie działającej
warstwy bezpieczeństwa po to, żeby naprawić rzecz, która jej nie dotyczy.
Patchowanie `channels` odrzucone: jego zachowanie nie jest błędne, a monkeypatch
byłby niewidoczny w `asgi.py` i pękłby przy aktualizacji.

**Leniwy start — w osobnym, długowiecznym zadaniu.** Sam klucz naprawia
uvicorna i **nie naprawia Daphne**, pod którym chodzi `run-site run`
i `channels_live_server` (§2.4).

Wersja 3 kazała wchodzić w `session_manager.run()` **z zadania żądania**. To
było błędne i jest przyczyną blokera BL-3 trzeciej recenzji:
`run()` to `async with lifespan, anyio.create_task_group()`
(`streamable_http_manager.py:145`), więc zadanie, które w to wchodzi, staje się
**host taskiem** grupy. Konsekwencje:

- jeśli w tym zadaniu jest aktywny **jakikolwiek inny cancel scope** (a §5.2
  każe owijać obsługę w `fail_after`), wyjście z niego rzuci
  `RuntimeError: Attempted to exit a cancel scope that isn't the current
  task's current cancel scope` (`anyio/_backends/_asyncio.py:470-474`).
  Pierwsze żądanie pada, grupa jest już oznaczona jako wystartowana
  (`_has_started`, `manager:143`), więc **każde kolejne też pada**;
- anulowanie host taska (timeout, `application_close_timeout` Daphne,
  `daphne/server.py:281-289`) **zatruwa grupę** — późniejsze `start()` kończy
  się `RuntimeError("Child exited without calling task_status.started()")`.
  Bez restartu procesu nie ma wyjścia, bo `run()` wchodzi się raz na instancję.

Dlatego host taskiem musi być **zadanie tła**, nigdy żądanie:

```python
class StartMcp:
    """Wejście w session_manager.run() dokładnie raz, w OSOBNYM zadaniu."""

    def __init__(self, mcp_app):
        self._app = mcp_app
        self._gotowe = asyncio.Event()
        self._zadanie: asyncio.Task | None = None
        self._blad: BaseException | None = None

    async def zapewnij(self) -> None:
        if self._zadanie is None:
            self._zadanie = asyncio.get_running_loop().create_task(self._trzymaj())
        await self._gotowe.wait()
        if self._blad is not None:
            raise RuntimeError("Menedżer sesji MCP nie wstał") from self._blad

    async def _trzymaj(self) -> None:
        """Host task grupy zadań — żyje tyle, co proces."""
        try:
            async with self._app.router.lifespan_context(self._app):
                self._gotowe.set()
                await asyncio.Event().wait()     # nigdy
        except BaseException as exc:             # noqa: BLE001 — re-raise przez zapewnij()
            self._blad = exc
            self._gotowe.set()
            raise
```

`zapewnij()` musi być **pierwszą instrukcją** w `RouterHttp`, przed założeniem
jakiegokolwiek scope'u (§5.2). `LifespanMcp` woła je na `lifespan.startup`;
pod Daphne pierwsze wywołanie przychodzi z pierwszego żądania. Tworzenie
zadania jest jednorazowe (`self._zadanie is None`), a `Event` szereguje
równoległych czekających — blokada nie jest potrzebna, bo `create_task`
w jednej pętli nie ma punktu przerwania między testem a przypisaniem.

**Błąd startu** raportujemy jako `lifespan.startup.failed` z komunikatem. Pod
gunicornem oznacza to `should_exit` w uvicornie (`lifespan/on.py:58-60`) →
worker pada → gunicorn respawnuje. Czyli **boot-loop, nie cisza** — i tak ma
być. Pod Daphne błąd wraca z `zapewnij()` jako 503 na `/mcp`.

**Zatrucie grupy mimo wszystko.** Wyjątek dziecka grupy poza `serve_connection`
anuluje scope grupy; pod uvicornem po starcie skutkuje to procesem, który żyje,
ale każde `/mcp` zwraca 500 aż do recyklingu `max_requests`. `StartMcp`
wystawia więc **stan gotowości** do healthchecku (§10.3), a `RouterHttp` przy
martwym zadaniu zwraca 503 zamiast 500.

**`RouterHttp`** — dopasowanie **dokładne**, nie prefiksowe:

| Ścieżka | Trafia do |
|---|---|
| `/mcp` | `BramkaBearera(tryb=publiczny)` → aplikacja MCP |
| `/mcp/auth` | `BramkaBearera(tryb=wymagany)` → **przepisanie ścieżki na `/mcp`** → aplikacja MCP |
| `/mcp/` | Django (strona HTML, §8) |
| reszta | Django |

**Przepisanie ścieżki jest obowiązkowe** (BL-1): SDK montuje trasę jako
`Route`, nie `Mount` (`lowlevel/server.py:808-813`), czyli regex `^/mcp$`.
Bez przepisania `/mcp/auth` dostałoby **404**, a `redirect_slashes` Starlette
próbowałoby jeszcze `/mcp/auth/`. Przepisujemy `scope["path"]` i `raw_path`
po przejściu przez bramkę.

Prefiksowe `/mcp*` z wersji 3 było też sprzeczne z §8: `/mcp/` trafiłoby do
Starlette i dostało 307 na `/mcp`.

`GET /mcp` z `Accept: text/html` (człowiek wkleił adres do przeglądarki)
przekierowujemy na `/mcp/` — inaczej SDK odda 406
(`streamable_http.py:698-703`).

### 5.2 `KontekstMcp` i `KlientScope` — dwie warstwy, nie jedna

Wersja 2 zakładała, że jedna warstwa przed aplikacją MCP ustawi wszystko.
**To było błędne dla IP klienta**: `ASGITransport` buduje scope wewnętrznego
żądania sam i wpisuje tam własne `client` (`httpx/_transports/asgi.py:92,117`).
Warstwa stojąca przed aplikacją MCP nie ma jak tego dosięgnąć.

Potrzebne są więc dwie:

**`KontekstMcp`** (przed aplikacją MCP) zdejmuje z zewnętrznego żądania i kładzie
w `ContextVar`:

| Co | Po co |
|---|---|
| `Host` | rozstrzygnięcie `Uczelnia` → bramka API i `ukryte_statusy` (§7.2) |
| scheme z `X-Forwarded-Proto` | inaczej `SECURE_SSL_REDIRECT` zapętla (§7.6) |
| IP z `get_client_ip` | throttling (§7.3) |
| bearer | przekazanie do wewnętrznego żądania |
| budżet czasu i współbieżności | D11 |

**`KlientScope`** (wokół `django_asgi_app`, czyli **za** transportem) nadpisuje
`scope["client"]` wartością z ContextVar. To jedyne miejsce, w którym da się to
zrobić.

Reset ContextVarów na wyjściu obowiązkowy.

**Sufit czasu (D11) — egzekwowany W KLIENCIE, nie wokół aplikacji.**

Timeouty `httpx` są przy `ASGITransport` martwe, a gunicornowy `timeout` to
heartbeat. Jedno `tools/call` rozwija się na N żądań do API bez żadnego limitu.

Wersja 3 kazała owinąć obsługę w `anyio.fail_after(...)` w `KontekstMcp`.
**To nie działa** (bloker BL-2 trzeciej recenzji). W trybie bezstanowym serwer
JSON-RPC startuje jako zadanie **grupy menedżera**
(`streamable_http_manager.py:243`), a handler narzędzia jest spawnowany do
grupy dispatchera (`jsonrpc_dispatcher.py:493,684`). `fail_after` wokół
`mcp_app(...)` anuluje wyłącznie zadanie żądania, które czeka na odpowiedź —
czyli:

- **narzędzie i jego N żądań do Django biegną dalej**, tylko nikt już na nie
  nie czeka;
- `http_transport.terminate()` **nie jest w `finally`** (`manager:246-249`),
  więc `read_stream` nigdy się nie zamyka → `run_stateless_server` żyje
  wiecznie → **wyciek zadania na każdy timeout**.

Ten sam wyciek zachodzi przy **każdym rozłączeniu klienta** w trakcie
`tools/call`, nie tylko przy timeoucie. Przy `proxy_read_timeout 300s` to
realny wektor wyczerpania zasobów: N rozłączeń = N wiecznych zadań.

Dlatego budżet trafia tam, gdzie faktycznie wykonuje się praca:

- `KontekstMcp` kładzie **deadline** (monotoniczny znacznik) i **semafor**
  w `ContextVar`;
- `BppClientInProcess` czyta deadline w `_request` i **sam podnosi `BppError`**,
  gdy budżet wyczerpany, a każde pojedyncze wywołanie owija w `fail_after`
  na resztkę budżetu;
- semafor ogranicza liczbę równoległych żądań wewnętrznych tego samego
  wywołania narzędzia.

Dzięki temu przekroczenie limitu **zatrzymuje pracę**, a nie tylko przestaje na
nią czekać — i wraca do klienta jako czytelny błąd narzędzia.

Wartości do ustalenia w planie; **istnienie limitu jest decyzją specu**.

**Wyciek przy rozłączeniu** jest niezależny od naszego budżetu i leży w SDK.
Do planu: zgłoszenie upstream oraz — do czasu naprawy — licznik żywych zadań
menedżera wystawiony w healthchecku (§10.3), żeby wyciek był widoczny, zanim
położy proces.

### 5.3 `BppClient` per żądanie (D9)

`BppClient` zapamiętuje `api_root` w `__init__`, `Config` jest `frozen`, a klient
z lifespanu jest jeden na proces (§2.2). Zamiast obchodzić to nadpisywaniem
prywatnego `_full_url`, korzystamy z furtki w kontrakcie `register_tools`:
lifespan oddaje **obiekt o tych samych atrybutach**, którego `client` jest
property:

```python
class KontekstZadania:
    """Spełnia kontrakt KontekstApp, ale klienta oddaje per żądanie."""

    bearer_provider = None          # host wielo-użytkownikowy — nigdy cache tokenu

    @property
    def client(self) -> BppClient:
        return klient_zadania.get()  # ContextVar, ustawiony przez KontekstMcp
```

`KontekstMcp` zakłada klienta na czas żądania:

```python
BppClientInProcess(
    Config(base_url=f"{scheme}://{host}", transport="stdio"),
    transport=httpx.ASGITransport(
        app=KlientScope(django_asgi_app),
        raise_app_exceptions=False,   # 500 → BppNetworkError, nie traceback
    ),
    tryb_auth=TrybAuth.W_PROCESIE,
    max_retries=0,
)
```

Rozwiązuje naraz: **`_api_root` z właściwego hosta**, **cache izolowany**
(świeży klient = świeży słownik, szew `_slownik_cache` niepotrzebny),
**semafor per żądanie**. Koszt to `AsyncClient` na żądanie — bez puli połączeń
i bez TLS to praktycznie sam obiekt Pythona.

`follow_redirects=False` (D12) — patrz §7.6.

Odziedziczona mechanika: retry martwy (`max_retries=0`), timeouty martwe (sufit
z §5.2), auto-follow paginacji i mapowanie błędów bez zmian.

### 5.4 `BramkaBearera` — własna warstwa 401 (D10)

SDK nie zna trybu „anonim dozwolony, zły token odrzucony" (§2.3): albo
`token_verifier` i 401 dla wszystkich bez tożsamości, albo brak weryfikacji
w ogóle. Piszemy więc własną warstwę ASGI **przed** aplikacją MCP, w dwóch
wariantach montażu:

| Adres | Brak nagłówka | Zły / wygasły / bez scope | Ważny |
|---|---|---|---|
| `/mcp` | przepuść jako anonim | **401** + `WWW-Authenticate` | przepuść z tożsamością |
| `/mcp/auth` | **401** + `WWW-Authenticate` | **401** + `WWW-Authenticate` | przepuść z tożsamością |

**Weryfikacja musi sprawdzać to samo, co DRF — nie mniej.**
`ApiReadOnlyForBearerMiddleware._ma_wazny_bearer` (`middleware.py:31-40`)
patrzy wyłącznie na `AccessToken.is_valid()`. `StrictOAuth2Authentication`
sprawdza dodatkowo `user.is_active` i scope `read`
(`authentication.py:33-35`). Gdyby `BramkaBearera` skopiowała tylko ten
pierwszy wzorzec, **token bez scope'u `read` przeszedłby bramkę i padł dopiero
w DRF** — czyli wróciłby jako błąd w treści JSON-RPC z HTTP 200, a klient nigdy
nie zrobiłby ponownej autoryzacji. Bramka musi więc sprawdzać: `is_valid()`
**oraz** `user.is_active` **oraz** scope `read`.

To jest **trzecia kopia** tych reguł w repo (obok `authentication.py`
i `middleware.py`). Wersja 2 specu proponowała konsolidację w
`oauth_mcp/tokens.py` i słusznie odsunąłem ją do projektu 3 jako zmianę
w testowanej warstwie auth — ale trzecia kopia jest ceną, którą trzeba nazwać.
**Do planu: minimalny wspólny helper czytany przez wszystkie trzy miejsca**,
bez ruszania struktury klas DRF. Pełna konsolidacja zostaje projektem 3.

Lookup idzie przez `sync_to_async` (kontekst async). Ponieważ dzieje się **poza
cyklem żądania Django** (brak sygnałów `request_started`/`request_finished`),
obowiązkowe jest `close_old_connections()` wokół zapytania — inaczej połączenia
do bazy nie są sprzątane.

**Dlaczego dwa adresy.** `/mcp` nigdy nie zmusi klienta do logowania, bo anonim
dostaje 200 — a czy klienci MCP odpalają OAuth przy 401 na **późniejszym**
żądaniu, jest nieznane i zależne od implementacji. `/mcp/auth` odrzuca 401-ką
już `initialize`, czyli w jedynym momencie, co do którego mamy pewność, że
obsługuje go każdy klient. Użytkownik wybiera adres świadomie, a projekt
przestaje zależeć od cudzego zachowania.

`WWW-Authenticate`:
`Bearer resource_metadata="https://<host>/.well-known/oauth-protected-resource"`

**`token_verifier` SDK nie jest używany** — jego montaż wyłączyłby anonima.

---

## 6. Discovery

Nowy widok w `oauth_mcp/views_metadata.py` —
`/.well-known/oauth-protected-resource` (RFC 9728), bliźniak istniejącego
RFC 8414, ten sam wzorzec `build_absolute_uri`:

```json
{ "resource": "https://<host>/mcp",
  "authorization_servers": ["https://<host>"],
  "scopes_supported": ["read"],
  "bearer_methods_supported": ["header"] }
```

Poprzedni spec (§6) przypisywał ten plik pakietowi `bpp-mcp`. **Przenosi się do
BPP** — Resource Serverem jest instancja.

### 6.1 Allowlista hostów aplikacji MCP

**[probe]** `TransportSecuritySettings` to druga, niezależna lista dozwolonych
hostów. Trzy rzeczy, których wersja 2 nie widziała:

1. **Inna semantyka niż `ALLOWED_HOSTS`** — dopasowanie dokładne albo `host:*`
   (`transport_security.py:49-60`). Django-owe `.domena` i `*` **nie działają**;
   trzeba je przetłumaczyć, a testy repo używają `ALLOWED_HOSTS = ["*"]`.
2. **Sprawdzany jest też `Origin`** (`:65-70`) — klienci przeglądarkowe
   i MCP Inspector go wysyłają. Niezgodny `Origin` daje **403**
   (`transport_security.py:113-114`), nie 421. Decyzja: `allowed_origins`
   wypełniamy tymi samymi hostami co `allowed_hosts`, ze schematem `https://`
   (plus `http://` dla `localhost` w dev).
3. **`host=` bez `transport_security` po cichu wyłącza ochronę**
   (`lowlevel/server.py:738-744`). Dlatego **zawsze** przekazujemy jawne
   `TransportSecuritySettings`.

Lista budowana **fabryką aplikacji** (`build_application()`), nie przy imporcie
modułu — inaczej `settings.ALLOWED_HOSTS` nadpisane w teście nigdy do niej nie
dotrze (§11).

---

## 7. Bezpieczeństwo

### 7.1 Przekazujemy WYŁĄCZNIE `Bearer`

Allowlista nagłówków wewnętrznego żądania: **`Authorization` tylko gdy schemat
to `Bearer`**, plus `Accept` i `Content-Type`. Odcinamy `Cookie`,
`X-Forwarded-*`, `Referer` i resztę.

- **`Cookie`** → `SessionAuthentication` (`base.py:1058`) uwierzytelnia sesją:
  pełne uprawnienia, bez zgody, bez scope, bez revoke. CSRF nie chroni, bo GET.
- **`Authorization: Basic`** → `BasicAuthentication` (`base.py:1059`)
  uwierzytelnia hasłem, a `ApiReadOnlyForBearerMiddleware` sprawdza **wyłącznie
  prefiks `bearer `** (`middleware.py:33`) — więc dla Basica warstwa read-only
  **nie istnieje**.

**Gdzie ta allowlista musi stać.** SDK przekazuje narzędziu **cały obiekt
`Request` zewnętrznego żądania** przez `SessionMessage.metadata.request`
(`streamable_http.py:608-611`) — z `Cookie` włącznie. Dziś czyta z niego tylko
`bearer_from_request` (`bpp_mcp/auth.py:46-53`), więc D6 jest w praktyce
zachowane, ale **przez dyscyplinę kodu w cudzym pakiecie, nie przez izolację**.
Nasza allowlista działa przy budowaniu żądania wewnętrznego
(`BppClientInProcess`), i to ona jest właściwą zaporą. Test „`Cookie` nie
uwierzytelnia" **musi być po stronie BPP**, nie tylko w `bpp-mcp` — bo to my
ponosimy skutki, gdyby tamta dyscyplina się zmieniła.

### 7.2 Propagacja `Host` — to jest kontrola dostępu

Wewnętrzne żądanie **musi** nieść `Host` zewnętrznego. Inaczej `Uczelnia=None`
(§2.5), a wtedy `BramkaApiV1` **przepuszcza bezwarunkowo** — API wyłączone przez
administratora staje się dostępne przez `/mcp` — a `ukryte_statusy=None`
przestaje filtrować rekordy ukrytych statusów. W instalacji wielouczelnianej to
wyciek między uczelniami.

### 7.3 Throttling

`ASGITransport` ustawia `client=("127.0.0.1", 123)`, więc bez interwencji
wszyscy anonimowi dzielą jeden kubełek. `KlientScope` (§5.2) wstawia IP
z `get_client_ip`. **Nie dokładamy `X-Forwarded-For`** — DRF bez `NUM_PROXIES`
kluczowałby po całym nagłówku (§2.5), a my chcemy `REMOTE_ADDR`.

Osobno: strefa nginx `bpp_api` (60 r/s) **jest omijana**, bo wewnętrzne żądania
nie przechodzą przez nginx, a jedno `tools/call` rozwija się na N żądań. Sufit
z D11 jest jedyną obroną na tej ścieżce — dlatego jest decyzją, nie pomiarem.

### 7.4 Rekurencja i zakres URL-i

`ASGITransport` dostaje `django_asgi_app`, nie `application`. `BppClientInProcess`
odrzuca ścieżki spoza `/api/v1/` **oraz sprawdza host** — `_full_url` przyjmuje
URL-e bezwzględne wprost (`client.py:183-184`), a paginacyjne `next` je niosą.

### 7.5 Widoczność i Rollbar

Wewnętrzne żądania nie trafiają do access-logu nginx ani uvicorna. Logujemy je
w `KontekstMcp` (ścieżka, kod, czas, obecność bearera — **nigdy token**).

`CustomRollbarNotifierMiddleware` (`base.py:346`) **nie obejmuje** wyjątków
z `LifespanMcp`, `KontekstMcp` ani aplikacji MCP — te nie trafią do Rollbara
same. Warstwa MCP woła `rollbar.report_exc_info()` jawnie i **nie wkłada
nagłówków do `extra_data`**. (`"authorization"` jest w `ROLLBAR_SCRUB_FIELDS`,
`base.py:1777`, ale to dotyczy żądań Django.)

**Wyjątki narzędzi wymagają osobnego przechwycenia.** SDK zamienia każdy
wyjątek handlera na `CallToolResult(is_error=True)` (`mcpserver/server.py:423-424`),
więc **nic nie dociera** do warstwy ASGI — jawne `report_exc_info()` tam by ich
nie zobaczyło. Potrzebny jest cienki wrapper wokół `register_tools`, który
owija każde zarejestrowane narzędzie i raportuje wyjątek, zanim SDK go zamieni
na wynik. Bez tego awarie narzędzi są **całkowicie niewidoczne** w monitoringu.

### 7.6 Przekierowania — `follow_redirects=False` (D12)

`BppClient` domyślnie podąża za przekierowaniami (`client.py:153`). W procesie
daje to dwa ciche problemy:

1. **`SECURE_SSL_REDIRECT=True`** (`production.py:168`) + scheme `http` → 301 na
   `https` → httpx podąża → **każde żądanie wewnętrzne wykonuje się dwa razy**,
   niewidocznie. Propagacja scheme (§5.2) tego unika, ale `follow_redirects`
   maskowałoby błąd, gdyby propagacja przestała działać.
2. **`FirstRunWizardMiddleware`** — `DEFAULT_SKIP_PREFIXES` to `/static/`,
   `/media/`, `/__debug__/`, `/admin/` (`first_run_wizard/middleware.py:22-27`),
   a `FIRST_RUN_WIZARD_SKIP_PREFIXES` nie jest ustawione. Na świeżej instalacji
   wewnętrzne `/api/v1/` **dostaje przekierowanie do kreatora**, httpx za nim
   idzie, `resp.json()` na HTML-u rzuca `ValueError`, którego `_request` nie
   mapuje (`client.py:271`) → surowy traceback w narzędziu. **To zamyka §15.6:
   tak, przekierowuje.**

Przy `follow_redirects=False` oba przypadki kończą się czytelnym `BppError` ze
statusem 301/302.

### 7.7 Co jeszcze wypada przez ominięcie middleware

Przegląd `MIDDLEWARE` (`base.py:328-351`) dla **zewnętrznego** `/mcp`:

| Middleware | Skutek |
|---|---|
| `SecurityMiddleware` | `/mcp` bez HSTS i nagłówków bezpieczeństwa — dokłada je nginx |
| `MaliciousRequestBlockingMiddleware` | `/mcp` poza filtrem botów — nowa powierzchnia bez tej siatki |
| `CountdownBlockingMiddleware` | **nie zwalnia `/api/`** (`django_countdown/middleware.py:22`): w trybie odliczania wewnętrzne żądania dostaną HTML blokady, a `/mcp` nie będzie blokowany. Decyzja: `/mcp` odbijamy **razem** z resztą serwisu |
| `FirstRunWizardMiddleware` | §7.6 |
| `CustomRollbarNotifierMiddleware` | §7.5 |
| `Session`/`CSRF`/`Auth`/`SessionSecurity`/`Axes` | nieistotne **pod warunkiem D6** |
| `LocaleMiddleware` | komunikaty narzędzi w domyślnym języku — kosmetyka |

---

## 8. Strona `/mcp/` dla człowieka

`GET /mcp/` → widok Django z instrukcją. `GET /mcp` z `Accept: text/html` →
redirect na `/mcp/` (§5.1). Treść wzorowana na `mcp.sentry.dev`: **oba adresy**
(publiczny i z logowaniem) z wyjaśnieniem różnicy, gotowe wklejki dla klientów,
link do `bpp-mcp` dla stdio. Adresy przez `build_absolute_uri`. Teksty przez
`gettext` (`LocaleMiddleware` działa dla tej ścieżki — idzie przez Django).

---

## 9. Zależności i obraz

Dochodzi `bpp-mcp>=0.4,<0.5`. **Zmierzone po faktycznym `uv lock`
(Task 1 planu): 21 nowych pakietów, nie dziesięć.** Wcześniejsze oszacowanie
liczyło tylko zależności bezpośrednie i było zaniżone ponad dwukrotnie —
poniżej stan rzeczywisty:

| Nowe | Uwaga |
|---|---|
| `httpx` | klient `BppClient` |
| **`httpx2`** | `mcp` 2.0 przeszło na drugą bibliotekę HTTP |
| `pydantic` | kompilowana, spora |
| `opentelemetry-api`, `jsonschema`, `mcp-types`, `python-multipart`, `sse-starlette`, `starlette`, `typing-inspection` | |

Zależności przechodnie, których pierwsze oszacowanie nie objęło:
`annotated-types`, `httpcore`, `httpcore2`, `httpx2-jsfetch`, `jsonschema`,
`jsonschema-specifications`, **`pydantic-core`**, `referencing`, **`rpds-py`**,
`truststore`, `typing-inspection`.

Już obecne: `anyio` (4.11.0), `pyjwt`, `uvicorn`.

**Dwa ustalenia, które podnoszą wagę ryzyka z §15:**

1. **`pydantic-core` i `rpds-py` to kompilowane rozszerzenia Rust** — osobne
   koła per platforma. To realny wzrost rozmiaru obrazu i osobna powierzchnia
   CVE dla bramki Trivy, której pierwsze oszacowanie w ogóle nie przewidywało.
2. **Dwa równoległe stosy HTTP w drzewie**: `bpp-mcp` zależy od `httpx`, a
   `mcp` 2.x od `httpx2` — każdy z własnym `httpcore`. Dochodzi też
   `httpx2-jsfetch` z markerem `sys_platform == 'emscripten'`, czyli kod WASM
   nieużywany w kontenerze Linux, ale obecny w locku. To wzmacnia argument za
   przejściem `bpp-mcp` na `httpx2` (§13, §15.5) — dziś wozimy oba.

**Kolizji `starlette` nie ma** — `channels[daphne]` ciągnie `asgiref` i `daphne`,
nie `starlette`. To zamyka §15.2.

Do sprawdzenia przed scaleniem:
- czy `mcp 2.0` nie wymaga `anyio` nowszego niż 4.11.0 (venv `bpp-mcp` ma 4.14.1),
- rozmiar obrazu produkcyjnego,
- **bramka Trivy** — dziesięć nowych pakietów to dziesięć nowych źródeł CVE
  w łańcuchu; `python-multipart` ma historię.

**`httpx` i `httpx2` naraz** to dublet, nie konflikt. Najczystsze wyjście wraca
do projektu 2: `bpp-mcp` przechodzi na `httpx2` (0.5.0) i przestaje wozić drugi
klient — pod warunkiem, że `httpx2` ma `ASGITransport` o tej samej semantyce,
bo na niej stoi D4. Poza zakresem tego specu (§13).

---

## 10. Wdrożenie

`bpp-deploy` **wymaga zmian**:

1. **ModSecurity/CRS** — wyłączenie obejmuje dziś tylko
   `^/(bpp|api/v1)/zapytanie/`. Ciało JSON-RPC na `/mcp`, zwłaszcza
   z DjangoQL w argumentach, będzie skanowane i 403 z WAF-a jest bardzo
   prawdopodobny. Potrzebne wyłączenie dla `/mcp`, zawężone jak istniejące.
2. **Strefa `limit_req`** — `/mcp` wpada dziś pod `location /` (100 r/s). Sufit
   z D11 działa **wewnątrz** aplikacji; strefa nginx chroni przed zalewem samych
   żądań MCP. Do zmierzenia, ale nie jest to już „poza zakresem" (§7.3).

3. **Healthcheck `/mcp`.** Grupa zadań menedżera może zostać „zatruta"
   (wyjątek dziecka anuluje scope grupy) — proces wtedy żyje, ale **każde
   `/mcp` zwraca błąd aż do recyklingu `max_requests`**. `StartMcp` wystawia
   stan gotowości i licznik żywych zadań; `RouterHttp` przy martwym zadaniu
   oddaje 503 zamiast 500, a monitoring ma po czym poznać, że endpoint padł
   mimo zdrowego procesu (§5.1, §5.2).

Bez zmian: `stateless_http` czyni recykling `--max-requests` nieszkodliwym,
`json_response` znosi problem `proxy_read_timeout`.

---

## 11. Testy

Konwencja repo: pytest, bez `unittest.TestCase`, `model_bakery.baker`.
**Repo nie ma `pytest-asyncio`** — korutyny odpala się wzorcem z
`django_bpp/tests/test_asgi_notifications.py:27` (`asyncio.run` w osobnym
wątku), więc dostęp do bazy wymaga `transaction=True` albo tego samego wzorca.

**Aplikacja musi być budowana fabryką** `build_application()`, nie tworzona przy
imporcie: (i) allowlista hostów SDK liczona z `settings` przy imporcie nie
zobaczy override'u z fixture'a `settings` (§6.1); (ii)
`session_manager.run()` można wejść **raz na instancję**, więc modułowe
`application` nie nadaje się do wielokrotnego lifespanu w testach.

**Routing i lifespan**
- klucz `"lifespan"` → `startup.complete`; błąd startu → `startup.failed`
- **leniwy start**: żądanie do `/mcp` **bez** lifespanu (symulacja Daphne)
  startuje menedżera i zwraca 200 — plus test, że drugie żądanie **nie**
  próbuje startować ponownie
- ruch spoza `/mcp` do Django; `websocket` do channels
- `GET /mcp` z `Accept: text/html` → redirect na `/mcp/`
- **`/mcp/auth` dociera do aplikacji MCP** — dowód, że przepisanie ścieżki
  działa (bez niego SDK dałoby 404, BL-1)
- `/mcp/` (ze slashem) trafia do **Django**, nie do Starlette
- start menedżera odbywa się w **osobnym zadaniu**: `zapewnij()` wywołane
  z zadania, w którym jest aktywny `fail_after`, **nie** psuje ani tego
  żądania, ani kolejnych (regresja na BL-3)
- po przekroczeniu budżetu czasu **narzędzie przestaje wykonywać żądania**
  do Django (licznik wywołań się nie zwiększa) — a nie tylko przestajemy
  czekać (regresja na BL-2)

**Bezpieczeństwo (każdy osobno)**
- `Cookie` wysłany do `/mcp` **nie** uwierzytelnia — także po wewnętrznym
  przekierowaniu (httpx ma własny cookie-jar, `_client.py:566`)
- `Authorization: Basic` **nie** jest przekazywany
- **test wielo-hostowy**: fixture'y są (`src/fixtures/conftest_multisite.py:16-48`,
  rejestracja `conftest.py:61`); domeny wymagają nadpisania `ALLOWED_HOSTS`
  per test (wzorzec: `admin_dashboard/tests/test_cache_vary_host.py:46`) — dwie
  `Uczelnia`, dwa hosty, każdy widzi swoje
- `api_v1_wlaczone=False` → `/mcp` też odmawia
- rekord o ukrytym statusie nie wycieka
- dwa różne IP → dwa kubełki throttlingu
- ścieżka **i host** spoza `/api/v1/` odrzucone (§7.4)
- `/mcp` bez tokenu → 200; `/mcp/auth` bez tokenu → **401** z `WWW-Authenticate`;
  zły token na obu → **401**

**Klient**
- `BppClientInProcess` zwraca to samo, co żądanie sieciowe
- cache izolowany między żądaniami
- przekierowanie kreatora → czytelny `BppError`, nie `ValueError` (§7.6)
- przekroczenie sufitu czasu → kontrolowany błąd (D11)

**Protokół**
- `initialize` → `tools/list` → `tools/call`, bez sieci; 11 narzędzi + 1 prompt
- klient testowy musi wysyłać `Content-Type: application/json`
  (`transport_security.py:96-100`)

**Ręcznie**
- podłączenie prawdziwego klienta Claude do obu adresów i pełny taniec OAuth

---

## 12. Kryteria akceptacji

- `POST /mcp` odpowiada na `initialize`, `tools/list`, `tools/call` bez tokenu,
  zwracając dane publiczne identyczne z `/api/v1/`.
- `POST /mcp/auth` bez tokenu → **401** z `WWW-Authenticate` wskazującym PRM.
- Zły token na obu adresach → **401**.
- `Cookie` i `Basic` **nie** uwierzytelniają.
- Dwie uczelnie na dwóch hostach widzą **swoje** dane; `api_v1_wlaczone=False`
  blokuje również `/mcp`.
- **`/mcp` działa pod Daphne** (`run-site run`) — leniwy start.
- `/.well-known/oauth-protected-resource` poprawne przy wielu hostach.
- `GET /mcp/` renderuje stronę z oboma adresami właściwymi dla hosta.
- Narzędzia z `bpp_mcp` — **żadnej kopii** w `src/`.
- Jawny sufit czasu **zatrzymuje pracę narzędzia**, nie tylko odpowiedź (D11).
- `/mcp/auth` dociera do aplikacji MCP (przepisanie ścieżki, BL-1).
- Menedżer sesji startuje w osobnym zadaniu i przeżywa żądanie, w którym go
  wywołano — także gdy w tym żądaniu był aktywny `fail_after` (BL-3).
- Healthcheck rozróżnia stan procesu od stanu endpointu MCP (§10.3).
- Testy zielone; `ruff` czysty; `pre-commit` bez uwag.
- Newsfragment w `src/bpp/newsfragments/`.
- Istniejące testy `oauth_mcp` i `api_v1` przechodzą **bez modyfikacji**.

---

## 13. Poza zakresem

- Narzędzia mutujące.
- **Rozszerzenie allowlisty DCR** o ChatGPT/Cursor — osobna decyzja (§1.1).
- Konsolidacja reguł tokenu — projekt 3 (§3).
- **Przejście `bpp-mcp` na `httpx2`** (0.5.0) — osobne wydanie (§9).
- WebMCP jako API przeglądarki.
- Wygaszenie `bpp-mcp`.
- Zasoby (`resources`) MCP. Prompt `zloz_zapytanie_djangoql` **wchodzi**, bo
  `register_tools` rejestruje go razem z narzędziami.
- RFC 8707 / audience binding.

Strefa `limit_req` **przestaje** być poza zakresem — patrz §10.2.

---

## 14. Rozliczenie z recenzjami

**Wersja 1 → 2:** bloker lifespanu potwierdzony, ale rozwiązywalny; bloker
hosta potwierdzony i groźniejszy (kontrola dostępu, nie błąd 400); dodane
`Basic`, cache, throttling, ModSecurity, allowlista DCR; 7 → 11 narzędzi;
zakres rozbity na trzy projekty.

**Wersja 2 → 3:** B1 (`base_url` per żądanie) → D9; B2 (Daphne) → leniwy start;
B3 (401 + PRM) → D10 dwa adresy; plus dwanaście poprawek.

**Wersja 3 → 4.** Trzecia recenzja **potwierdziła D9 jako zamknięte** i wskazała
trzy nowe blokery — wszystkie w rozwiązaniach B2/B3, nie w architekturze:

| Ustalenie | Rozstrzygnięcie w tej wersji |
|---|---|
| **BL-1** `/mcp/auth` → 404; SDK montuje `Route` (`^/mcp$`), nie `Mount` | `RouterHttp` **przepisuje ścieżkę** na `/mcp` po bramce; dopasowanie dokładne, nie prefiksowe (§5.1) |
| **BL-2** `fail_after` wokół aplikacji nie zatrzymuje narzędzia i wycieka zadanie | budżet i semafor **w `BppClientInProcess`**, egzekwowane w `_request` (§5.2) |
| **BL-3** leniwy start pęka pod własnym `fail_after`; anulowanie hosta zatruwa grupę | start w **osobnym, długowiecznym zadaniu**; `zapewnij()` przed jakimkolwiek scope'em (§5.1) |
| bramka sprawdzała mniej niż DRF (brak scope, `is_active`) | pełny zestaw reguł + `close_old_connections` (§5.4) |
| `KlientScope` bez decyzji o pustym ContextVar | fail-closed (§5.2) |
| `Origin` → 403, nie 421; brak reguły dla `allowed_origins` | §6.1 |
| Rollbar nie zobaczy wyjątków narzędzi | wrapper wokół `register_tools` (§7.5) |
| `Cookie` dociera do narzędzia przez `SessionMessage` | nazwane; test po stronie BPP (§7.1) |
| wyciek zadania przy **każdym** rozłączeniu klienta | nazwane, healthcheck + zgłoszenie upstream (§5.2, §10.3) |
| zatrucie grupy także pod uvicornem | healthcheck, 503 zamiast 500 (§10.3) |
| `Uczelnia=None` przesadzone dla single-site | sprostowane — dotyczy wielouczelnianości (§2.5) |
| `stateless + GET → 405` niepotwierdzone | wycofane z §2.3, test warunkowy (§11) |
| dwie ścieżki protokołu, różny czas życia | §2.3, uwzględnione w §5.2 |

**Wycofane twierdzenia wersji 3:** „B2 zamknięty przez D2" i „B3 zamknięty przez
D10" — obie były przedwczesne; zamykają je dopiero poprawki tej wersji.
„Rollbar zamyka §15.7" — nie obejmowało wyjątków narzędzi.

---

## 15. Otwarte kwestie

Zamknięte: **§15.1 wersji 2** (kształt endpointu → D10); **`starlette`** (brak
kolizji, §9); **kreator przekierowuje** (tak, §7.6); **Rollbar** (§7.5);
**`anyio`** — `mcp 2.0` wymaga `>=4.9`, BPP ma 4.11.0 (§9).

Zostają:

1. Wpływ dziesięciu nowych pakietów na bramkę Trivy i rozmiar obrazu (§9).
2. Wartości budżetu czasu i semafora (D11) — pomiar; **istnienie limitu jest
   zdecydowane** (§5.2).
3. Kształt reguły wyłączającej ModSecurity dla `/mcp` (§10.1).
4. Czy strefa `limit_req` dla `/mcp` jest potrzebna (§10.2).
5. Czy `httpx2` ma `ASGITransport` o semantyce wymaganej przez D4 — warunek
   przejścia `bpp-mcp` na jeden klient HTTP (§9, §13).
6. Czy `stateless_http` + `GET` daje 405 — do sprawdzenia przed napisaniem
   testu (§2.3, §11).
7. Czy klienci Claude walidują pole `resource` w PRM względem adresu serwera —
   przy dwóch adresach (`/mcp`, `/mcp/auth`) może wymagać metadanych pod
   `/.well-known/oauth-protected-resource/<ścieżka>` (RFC 9728 §3.1). **Do
   sprawdzenia ręcznie na obu adresach.**
8. Zgłoszenie upstream braku `terminate()` w `finally`
   (`streamable_http_manager.py:246-249`) — wyciek zadania przy rozłączeniu
   klienta (§5.2).
