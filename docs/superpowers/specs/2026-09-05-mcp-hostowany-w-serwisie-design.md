# Hostowany serwer MCP w serwisie BPP (`/mcp`) — projekt 1 z 3

Data: 2026-09-05 (wersja 3, 2026-09-06)
Status: projekt do zatwierdzenia
Poprzednik: `2026-07-11-mcp-oauth-authorization-design.md` (warstwa OAuth po
stronie BPP — **zrealizowana**, `src/oauth_mcp/`)

> **Historia dokumentu.** Wersja 1 dostała werdykt „wymaga przeprojektowania".
> Wersja 2 (przepisana po pierwszej recenzji i dwóch probe'ach) dostała
> „niewdrażalne — trzy blokery". Ta wersja zamyka B1–B3 i dwanaście poprawek.
> Rozliczenie w §14.

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
- `stateless_http=True` + `GET` → **405** (`streamable_http.py:788-790,848`),
  nie SSE.
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
`Uczelnia.objects.get_for_request`). Czyli **request z nieznanym hostem omija
wszystkie sześć przełączników API**, a `UkryjStatusyKorektyMixin.ukryte_statusy`
daje `None` (`viewsets/common.py:9-13`) → rekordy ukrytych statusów przestają
być filtrowane.

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
| D2 | Klucz `"lifespan"` w istniejącym `ProtocolTypeRouter` **+ leniwy start** | klucz naprawia uvicorna; leniwy start naprawia Daphne (§2.4, §5.1) |
| D3 | `stateless_http=True` + `json_response=True` | recykling workera zabiłby sesję stateful; `json_response` znosi SSE |
| D4 | Dane przez `httpx.ASGITransport` na `django_asgi_app` | ta sama ścieżka kodu, bez gniazda |
| D5 | Wewnętrzne żądanie dziedziczy `Host`, scheme i IP klienta | inaczej `Uczelnia=None` → obejście bramki i wyciek (§7.2) |
| D6 | Przekazujemy **wyłącznie `Bearer`** | inaczej Basic i sesja omijają model OAuth (§7.1) |
| D7 | Polityka dostępu dziedziczona z `/api/v1/` | anonim czyta publiczne, bearer odblokowuje resztę |
| D8 | Read-only | narzędzia wykonują wyłącznie GET |
| **D9** | **`BppClient` per żądanie**, przez property w obiekcie lifespanu | `_api_root` zapamiętany w `__init__` (§2.2); rozwiązuje też cache i semafor |
| **D10** | **Dwa adresy: `/mcp` (publiczny) i `/mcp/auth` (zawsze 401 bez tokenu)** | SDK nie zna trybu „anonim tak, zły token nie" (§2.3); dwa adresy usuwają zależność od nieznanego zachowania klientów |
| **D11** | **Jawny sufit czasu i współbieżności** w naszej warstwie | timeouty `httpx` martwe przy `ASGITransport`, gunicornowy `timeout` to heartbeat (§2.4) |
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

**Leniwy start.** Sam klucz naprawia uvicorna i **nie naprawia Daphne**, pod
którym chodzi `run-site run` i `channels_live_server` (§2.4). Dlatego start
menedżera sesji jest **idempotentny i wyzwalany z obu stron**:

```python
class StartMcp:
    """Wejście w session_manager.run() dokładnie raz, skądkolwiek przyjdzie."""

    def __init__(self, mcp_app):
        self._app = mcp_app
        self._lock = anyio.Lock()
        self._stack: AsyncExitStack | None = None

    async def zapewnij(self) -> None:
        if self._stack is not None:
            return
        async with self._lock:
            if self._stack is not None:      # double-check pod blokadą
                return
            stack = AsyncExitStack()
            await stack.enter_async_context(
                self._app.router.lifespan_context(self._app)
            )
            self._stack = stack
```

`LifespanMcp` woła `zapewnij()` na `lifespan.startup`; `RouterHttp` woła je
przed pierwszym żądaniem do `/mcp*`. Pod uvicornem zadziała pierwsze, pod
Daphne — drugie. **`session_manager.run()` można wejść raz na instancję**
(`streamable_http_manager.py:137-143`), więc blokada i double-check są
obowiązkowe, nie ozdobne.

Kontekst zadania: `run()` zakłada grupę zadań anyio, która żyje tak długo, jak
kontekst, w którym ją utworzono. Przy starcie z żądania trzymamy `AsyncExitStack`
w obiekcie modułowym, więc nie ginie z żądaniem — **to jest miejsce wymagające
własnego testu**, nie założenia (§11).

**Błąd startu** raportujemy jako `lifespan.startup.failed` z komunikatem. Pod
gunicornem oznacza to `should_exit` w uvicornie (`lifespan/on.py:58-60`) →
worker pada → gunicorn respawnuje. Czyli **boot-loop, nie cisza** — i tak ma
być: awaria startu MCP nie może przejść niezauważona.

**`RouterHttp`** rozdziela po **ścieżce**, nie po metodzie. `GET /mcp`
z `Accept: text/html` (człowiek wkleił adres do przeglądarki) przekierowujemy
na `/mcp/` — inaczej SDK odda 406 „Client must accept text/event-stream"
(`streamable_http.py:698-703`). Aplikacja MCP sama routuje na
`streamable_http_path`, więc **nie obcinamy prefiksu**.

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

**Sufit czasu (D11).** Timeouty `httpx` są przy `ASGITransport` martwe, a
gunicornowy `timeout` to heartbeat. Jedno `tools/call` rozwija się na N żądań do
API bez żadnego limitu. `KontekstMcp` owija obsługę w `anyio.fail_after(...)`
i trzyma semafor ograniczający liczbę równoległych żądań wewnętrznych. Wartości
do ustalenia w planie, ale **istnienie limitu jest decyzją specu**, nie
„pomiarem na później".

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

Weryfikacja tokenu to lookup w tej samej bazie — wzorzec z
`ApiReadOnlyForBearerMiddleware._ma_wazny_bearer` (`middleware.py:31-40`),
opakowany w `sync_to_async` (kontekst async).

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
   i MCP Inspector go wysyłają; pusta lista `allowed_origins` + obecny `Origin`
   → 421.
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
`base.py:1777`, ale to dotyczy żądań Django — zamyka §15.7.)

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

Dochodzi `bpp-mcp>=0.4,<0.5`. **Delta policzona** przeciwko `uv.lock` BPP —
dziesięć nowych pakietów:

| Nowe | Uwaga |
|---|---|
| `httpx` | klient `BppClient` |
| **`httpx2`** | `mcp` 2.0 przeszło na drugą bibliotekę HTTP |
| `pydantic` | kompilowana, spora |
| `opentelemetry-api`, `jsonschema`, `mcp-types`, `python-multipart`, `sse-starlette`, `starlette`, `typing-inspection` | |

Już obecne: `anyio` (4.11.0), `pyjwt`, `uvicorn`.

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
- `GET /mcp` bez tego nagłówka przy `stateless_http` → **405** (nie SSE)

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
- Jawny sufit czasu i współbieżności działa (D11).
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

**Wersja 1 → 2** (pierwsza recenzja): bloker lifespanu potwierdzony, ale
rozwiązywalny; bloker hosta potwierdzony i groźniejszy (kontrola dostępu, nie
błąd 400); dodane `Basic`, cache, throttling, ModSecurity, allowlista DCR;
poprawione 7 → 11 narzędzi; zakres rozbity na trzy projekty.

**Wersja 2 → 3** (druga recenzja):

| Ustalenie | Rozstrzygnięcie |
|---|---|
| **B1** `base_url` per żądanie niewykonalne z 0.4.0 | **D9** — klient per żądanie przez property w obiekcie lifespanu; zero zmian w `bpp-mcp` (§5.3) |
| **B2** lifespan nie działa pod Daphne (dev, Playwright) | **D2** — leniwy start idempotentny, wyzwalany z obu stron (§5.1) |
| **B3** brak wykonawcy 401 + PRM; `token_verifier` kasuje anonima | **D10** — własna `BramkaBearera` i **dwa adresy** (§5.4) |
| IP klienta nieosiągalne przed aplikacją MCP | `KlientScope` za transportem (§5.2) |
| scheme i `SECURE_SSL_REDIRECT` | propagacja + `follow_redirects=False` (§7.6) |
| semantyka allowlisty SDK, `Origin`, `host=` bez `transport_security` | §6.1 |
| `FirstRunWizardMiddleware` przekierowuje | potwierdzone, **zamyka §15.6** (§7.6) |
| brak sufitu czasu | **D11** (§5.2) |
| `GET /mcp` → 406 | redirect przy `Accept: text/html` (§5.1) |
| Rollbar nie obejmuje warstwy MCP | jawne `report_exc_info` (§7.5), **zamyka §15.7** |
| throttling po całym XFF | nie dokładamy XFF (§7.3) |
| `startup.failed` → boot-loop | nazwane jako oczekiwane (§5.1) |
| testy: fabryka, brak `pytest-asyncio`, `run()` raz | §11 |
| `stateless_http` + GET → 405, nie SSE | §11 |
| numery linii `views_dcr`, `channels/routing` | poprawione (§2.1, §2.4) |
| `CountdownBlockingMiddleware` nie zwalnia `/api/` | §7.7 |

**Nieprawdziwe twierdzenia wersji 2, wycofane:** „szew cache rozwiązuje problem
współdzielenia" (rozwiązywał połowę — `_api_root` został, D9 rozwiązuje oba);
„throttling potwierdzony" (problem tak, mechanizm naprawy nie istniał);
„lifespan rozwiązany jednym kluczem" (tylko pod uvicornem).

---

## 15. Otwarte kwestie

Zamknięte w tej wersji: **§15.1** (kształt endpointu → D10), **§15.2**
(`starlette` — brak kolizji, §9), **§15.6** (kreator przekierowuje — tak, §7.6),
**§15.7** (Rollbar — §7.5).

Zostają:

1. Czy `mcp 2.0` wymaga `anyio` nowszego niż 4.11.0 z `uv.lock` (§9).
2. Wpływ dziesięciu nowych pakietów na bramkę Trivy i rozmiar obrazu (§9).
3. Wartości sufitu czasu i współbieżności (D11) — do ustalenia pomiarem, ale
   **istnienie limitu jest już zdecydowane**.
4. Kształt reguły wyłączającej ModSecurity dla `/mcp` (§10.1).
5. Czy strefa `limit_req` dla `/mcp` jest potrzebna (§10.2).
6. Czy `httpx2` ma `ASGITransport` o semantyce wymaganej przez D4 — warunek
   wstępny dla przejścia `bpp-mcp` na jeden klient HTTP (§9, §13).
7. **Trwałość grupy zadań anyio przy leniwym starcie** — `run()` wchodzony
   z kontekstu żądania, a `AsyncExitStack` trzymany w obiekcie modułowym.
   Do potwierdzenia testem pod Daphne (§5.1, §11).
