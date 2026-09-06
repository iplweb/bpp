# Hostowany serwer MCP w serwisie BPP (`/mcp`) — projekt 1 z 3

Data: 2026-09-05 (przepisany 2026-09-06)
Status: projekt do zatwierdzenia
Poprzednik: `2026-07-11-mcp-oauth-authorization-design.md` (warstwa OAuth po
stronie BPP — **zrealizowana**, `src/oauth_mcp/`)

> **Ten dokument został przepisany.** Pierwsza wersja (commit poprzedzający)
> dostała od recenzji werdykt „wymaga przeprojektowania". Dwa blokery
> potwierdzono, jeden zdegradowano po weryfikacji empirycznej, cztery dziury
> bezpieczeństwa dopisano. Wszystkie zmiany są opisane w §14.

---

## 1. Cel i motywacja

Dostęp AI do danych BPP idzie dziś przez `bpp-mcp` — pakiet z PyPI, który
użytkownik instaluje do swojego klienta MCP jako serwer stdio. Trzy koszty:

1. **Próg wejścia.** Potrzebny Python i `uvx`, a przede wszystkim użytkownik
   musi **znać i wpisać adres swojej instancji** (`BPP_BASE_URL` celowo bez
   wartości domyślnej — każde wdrożenie to inna uczelnia).
2. **Odcięta kategoria klientów.** Klienci webowi (claude.ai) i urządzenia
   mobilne **nie mają jak uruchomić procesu lokalnego**.
3. **Skos wersji.** N wersji pakietu × M wdrożeń BPP.

**Cel:** BPP wystawia własny endpoint MCP pod `/mcp`, wyjeżdżający z tym samym
obrazem dockerowym co reszta serwisu. Użytkownik wkleja adres swojej instancji
z dopiskiem `/mcp` i to jest cała konfiguracja.

### 1.1 Zasięg — uczciwie

Pierwsza wersja tego specu obiecywała „claude.ai, ChatGPT, Cursor, VS Code".
**To była nieprawda.** Allowlista redirect_uri w DCR
(`src/oauth_mcp/views_dcr.py:17-23`) dopuszcza wyłącznie:

```
https://claude.ai/*      https://*.claude.ai/*      https://claude.com/*
http://localhost[:port]/*                            http://127.0.0.1[:port]/*
```

ChatGPT i Cursor **nie zarejestrują klienta** — dostaną odmowę na DCR.
Realny zasięg tej pracy to **ekosystem Claude** (web, desktop, Code) plus
klienci lokalne. Rozszerzenie allowlisty jest osobną decyzją bezpieczeństwa,
poza zakresem (§13).

Dostęp anonimowy nie wymaga DCR w ogóle, więc **publiczna część działa
z każdym klientem** obsługującym zdalne MCP. Ograniczenie dotyczy tylko
logowania.

---

## 2. Kontekst — ustalenia z kodu i z probe'ów

Numery linii wg `dev` @ `31d3d4612`. Ustalenia oznaczone **[probe]** pochodzą
z uruchomionego kodu, nie z lektury.

### 2.1 Warstwa OAuth po stronie BPP — istnieje i jest kompletna

| Element | Plik |
|---|---|
| `/o/authorize/`, `/o/token/`, `/o/revoke_token/` | `oauth_mcp/urls.py` |
| DCR `/o/register/` (RFC 7591) + allowlista + rate-limit | `oauth_mcp/views_dcr.py` |
| AS metadata `/.well-known/oauth-authorization-server` (RFC 8414) | `oauth_mcp/views_metadata.py` |
| `StrictOAuth2Authentication` — bearer → `request.user`, twarde 401 | `oauth_mcp/authentication.py` |
| `ApiReadOnlyForBearerMiddleware` — mutacje `/api/v1/` bearerem → 403 | `oauth_mcp/middleware.py` |
| `WhoAmIView` — **routing w `api_v1/urls.py:265`**, pod `z_bramka_api_v1` | `oauth_mcp/views_whoami.py` |
| revoke przy zmianie hasła / dezaktywacji | `oauth_mcp/signals.py` |

`StrictOAuth2Authentication` jest **pierwsza** w
`REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]` (`base.py:1057`), przed
`SessionAuthentication` (1058) i `BasicAuthentication` (1059).

### 2.2 Pakiet `bpp-mcp` 0.4.0 — szwy gotowe

Wydany dziś (projekt 2, PR-y #21–#23). Wystawia:

- `register_tools(mcp)` — **11 narzędzi + 1 prompt** na instancji `MCPServer`
  hosta. (Pierwsza wersja specu mówiła o siedmiu i twierdziła, że rejestrowane
  są funkcje z `tools.py`; w rzeczywistości to wrappery z `server.py`, biorące
  klienta z `ctx.request_context.lifespan_context`.)
- `KontekstApp` — kontrakt lifespanu (`client`, `bearer_provider`).
- `BppClient(transport=...)` — wstrzykiwany transport `httpx`.
- `TrybAuth.W_PROCESIE` — bearer albo anonim, **nigdy Basic**.
- `BppClient._slownik_cache()` — szew pod cache o zasięgu per-żądanie.

### 2.3 MCP SDK 2.0 — ustalenia z probe'ów

- **[probe]** `stateless_http` i `json_response` **nie są parametrami
  konstruktora** `MCPServer` — mieszkają w `streamable_http_app()`.
- **[probe]** `POST /mcp` **bez wejścia w lifespan** kończy się
  `RuntimeError: Task group is not initialized. Make sure to use run().`
  Dotyczy również `stateless_http=True`.
- **[probe]** Po wejściu w lifespan aplikacji ta sama ścieżka oddaje **200**
  z poprawną odpowiedzią `initialize`.
- **[probe]** Aplikacja MCP ma **własną allowlistę hostów**
  (`TransportSecuritySettings`), niezależną od `ALLOWED_HOSTS` Django. Nieznany
  `Host` → **421 Invalid Host header**.
- W SDK 2.0 **lifespan wchodzi RAZ na serwer**, nie per sesja — jego wynik
  dzielą wszystkie sesje i żądania (docstring `bpp_mcp/server.py`).

### 2.4 Infrastruktura

- ASGI: `src/django_bpp/asgi.py` — `ProtocolTypeRouter` z
  `{"http": django_asgi_app, "websocket": ...}`. **`ProtocolTypeRouter` rzuca
  `ValueError` na scope `lifespan`**, a uvicorn w trybie `auto` loguje to jako
  „appears unsupported" i jedzie dalej — czyli błąd jest cichy.
- Produkcja: `gunicorn django_bpp.asgi:application` z `UvicornWorker`;
  `max_requests=1000` + jitter 200 w `docker/appserver/gunicorn_conf.py`
  (**nie** w entrypoincie). Gałąź dev to `uvicorn --reload` bez gunicorna.
- nginx (`bpp-deploy`): trzy strefy `limit_req` (`_bpp-locations.conf:74-89`) —
  `/api/` 60 r/s burst 60, `/admin/` 50 r/s, `/` 100 r/s burst 100.
- **ModSecurity/CRS** przed appserverem; jedyne wyłączenie dla DjangoQL to
  `^/(bpp|api/v1)/zapytanie/` (`modsecurity-override.conf.template:79`).
- `api_v1.pagination.BppLimitOffsetPagination` — `MAKS_LIMIT = 500`, **cichy
  clamp pojedynczej strony** (nie odmowa).

### 2.5 Bramka API i model tożsamości hosta

To jest źródło najgroźniejszego problemu w §7.2. Kolejność w
`BramkaApiV1` (`src/api_v1/permissions.py`), cytat z docstringu:

> 1. uczelnia nierozstrzygnięta (pusta baza, kreator konfiguracji, brak
>    mapowania Site→Uczelnia) → **przepuszczamy**, bo nie ma kto podjąć decyzji

`Uczelnia` rozstrzyga się z nagłówka `Host` (`SiteResolutionMiddleware`,
`Uczelnia.objects.get_for_request`). Czyli: **request z nieznanym hostem omija
wszystkie sześć przełączników API.** Do tego
`UkryjStatusyKorektyMixin.ukryte_statusy` daje wtedy `None` → rekordy ukrytych
statusów przestają być filtrowane.

`SearchAnonThrottle` (`api_v1/throttling.py`) dziedziczy po `AnonRateThrottle`,
czyli **liczy po IP**.

---

## 3. Trzy projekty, nie jeden

Recenzja pierwszej wersji słusznie wskazała, że dokument mieszał trzy
niezależne przedsięwzięcia. Rozbicie:

| # | Projekt | Status |
|---|---|---|
| 1 | **Hosting MCP w BPP** — dyspozytor, klient w procesie, discovery, strona | **ten spec** |
| 2 | Szwy w `bpp-mcp` | **zrobione** — 0.4.0 na PyPI |
| 3 | Konsolidacja reguł tokenu w `oauth_mcp/tokens.py` | osobny spec, §13 |

Projekt 3 wypada z zakresu świadomie: to zmiana w **testowanej warstwie
uwierzytelniania**, i wrzucanie jej do środka feature'a było błędem. Ten spec
konsumuje istniejące `StrictOAuth2Authentication` bez ruszania go.

---

## 4. Decyzje architektoniczne

| # | Decyzja | Uzasadnienie |
|---|---|---|
| D1 | Narzędzia z `bpp-mcp` (zależność), zero kopii w `src/` | jedna implementacja, zero rozjazdu |
| D2 | Montaż: **własny dyspozytor ASGI** zamiast `ProtocolTypeRouter` | `ProtocolTypeRouter` nie obsługuje `lifespan`, a bez niego menedżer sesji nie wstaje **[probe]** |
| D3 | `stateless_http=True` + `json_response=True` | recykling workera zabiłby sesję stateful; `json_response` znosi SSE, więc `proxy_read_timeout 300s` przestaje być tematem |
| D4 | Dane przez `httpx.ASGITransport` na `django_asgi_app` | ta sama ścieżka kodu co przez sieć, bez gniazda |
| D5 | Wewnętrzne żądanie **dziedziczy `Host`, scheme i IP klienta** z zewnętrznego | inaczej `Uczelnia=None` → obejście bramki i wyciek (§2.5) |
| D6 | Przekazujemy **wyłącznie `Bearer`**, nigdy surowy `Authorization` ani `Cookie` | inaczej Basic i sesja omijają model OAuth (§7.1) |
| D7 | Polityka dostępu dziedziczona z `/api/v1/` | anonim czyta publiczne, bearer odblokowuje resztę |
| D8 | Read-only | narzędzia wykonują wyłącznie GET |

### 4.1 Co zostało obalone z pierwszej wersji

Pierwsza wersja proponowała `config.api_root` wskazujący na
`http://bpp.invalid/api/v1` z uzasadnieniem „host jest nieużywany przy
`ASGITransport`". **To było fałszywe na trzech poziomach naraz** —
`ALLOWED_HOSTS`, `SECURE_SSL_REDIRECT` i przede wszystkim rozstrzyganie
`Uczelnia` z hosta (§2.5). Zastąpione przez D5.

---

## 5. Architektura

```
                   gunicorn + UvicornWorker
                             │
               django_bpp.asgi:application  =  Dyspozytor
                             │
        ┌────────────────────┼────────────────────┐
   scope=lifespan      scope=http            scope=websocket
        │                    │                     │
  lifespan aplikacji   ┌─────┴─────┐          channels
    MCP (nasz!)     /mcp*      reszta
                       │           │
              KontekstMcpMiddleware│
                       │           │
              aplikacja MCP        │
                       │           │
              register_tools       │
                       │           │
        BppClientInProcess ────────┴──→ django_asgi_app
              (ASGITransport)
```

### 5.1 Dyspozytor — rozwiązanie blokera lifespanu

`ProtocolTypeRouter` z channels rzuca `ValueError` na scope `lifespan`, więc
menedżer sesji MCP nigdy nie wstaje. Probe potwierdził objaw i potwierdził, że
**wystarczy samemu obsłużyć ten scope**:

```python
class Dyspozytor:
    """Zastępuje ProtocolTypeRouter: trzy scope'y zamiast dwóch."""

    async def __call__(self, scope, receive, send):
        if scope["type"] == "lifespan":
            await self._lifespan(scope, receive, send)   # nasz, dla MCP
        elif scope["type"] == "http" and self._to_mcp(scope["path"]):
            await self._mcp(scope, receive, send)
        elif scope["type"] == "websocket":
            await self._ws(scope, receive, send)         # channels
        else:
            await self._django(scope, receive, send)
```

`_lifespan` na `lifespan.startup` wchodzi w
`self._mcp.router.lifespan_context(self._mcp)`, na `lifespan.shutdown` z niego
wychodzi, a błąd startu raportuje jako `lifespan.startup.failed` — **nie
połyka go**, inaczej wracamy do cichej awarii, tylko innej.

`_to_mcp` dopasowuje **ścieżkę**, nie metodę: SDK obsługuje na trasie
streamable również `GET` (SSE) i `DELETE`. Rozdzielenie „POST do protokołu, GET
do HTML-a" z pierwszej wersji było błędne.

Aplikacja MCP sama routuje na `streamable_http_path` (domyślnie `/mcp`), więc
dyspozytor **nie obcina prefiksu**.

### 5.2 Kontekst żądania — `KontekstMcpMiddleware`

Cienka warstwa ASGI przed aplikacją MCP. Zdejmuje z **zewnętrznego** żądania to,
czego wewnętrzne nie ma skąd wziąć, i zapisuje w `ContextVar`:

| Co | Po co |
|---|---|
| `Host` | rozstrzygnięcie `Uczelnia` → bramka API i `ukryte_statusy` (§2.5) |
| scheme | `build_absolute_uri`, brak pętli `SECURE_SSL_REDIRECT` |
| IP klienta | throttling `SearchAnonThrottle` liczy po IP (§7.3) |
| bearer (jeśli jest) | przekazanie do wewnętrznego żądania |
| świeży słownik cache | izolacja `_slownik_cache()` per żądanie |

Reset na wyjściu obowiązkowy — klient MCP żyje w lifespanie, czyli między
żądaniami, a `ContextVar` bez resetu wycieka do następnego.

### 5.3 `BppClientInProcess`

```python
class BppClientInProcess(BppClient):
    def __init__(self, config, **kw):
        super().__init__(
            config,
            transport=httpx.ASGITransport(
                app=django_asgi_app,          # NIE `application` — rekurencja
                raise_app_exceptions=False,   # 500 → BppNetworkError, nie traceback
            ),
            tryb_auth=TrybAuth.W_PROCESIE,
            max_retries=0,                    # nie ma sieci do ponowienia
            **kw,
        )

    def _slownik_cache(self):
        return cache_zadania.get()            # ContextVar z §5.2
```

`config.base_url` składamy **per żądanie** z `Host` i scheme zewnętrznego
żądania. Host `bpp.invalid` z pierwszej wersji jest wycofany (§4.1).

Odziedziczona mechanika:

| Element | W procesie |
|---|---|
| retry + backoff | **martwy** (`max_retries=0`) |
| timeouty `httpx` | **martwe** — `ASGITransport` ich nie czyta; sufit musi dać host |
| semafor (8) | **zostaje** — dławi równoległe rozwijanie hyperlinków |
| cache | **przekierowany** na słownik per-żądanie |
| auto-follow paginacji | **zostaje** |
| mapowanie błędów | **zostaje** |

---

## 6. Uwierzytelnianie i discovery

### 6.1 Przepływ

```
brak Bearera            → wewnętrzne żądanie bez Authorization → AnonymousUser
ważny Bearer            → przekaż WYŁĄCZNIE ten nagłówek → StrictOAuth2Authentication
nieważny / zły scope    → 401 + WWW-Authenticate
```

### 6.2 Discovery

Nowy widok w `oauth_mcp/views_metadata.py` — `/.well-known/oauth-protected-resource`
(RFC 9728), bliźniak istniejącego RFC 8414, ten sam wzorzec `build_absolute_uri`:

```json
{ "resource": "https://<host>/mcp",
  "authorization_servers": ["https://<host>"],
  "scopes_supported": ["read"],
  "bearer_methods_supported": ["header"] }
```

Nagłówek przy 401:
`Bearer resource_metadata="https://<host>/.well-known/oauth-protected-resource"`

Poprzedni spec (§6) przypisywał ten plik pakietowi `bpp-mcp`. **Przenosi się do
BPP** — Resource Serverem jest instancja.

### 6.3 Allowlista hostów aplikacji MCP

**[probe]** `TransportSecuritySettings` to druga, niezależna od Django lista
dozwolonych hostów; nieznany `Host` → 421. Zasilamy ją z `ALLOWED_HOSTS`
(i `DJANGO_BPP_HOSTNAMES` w instalacji wielouczelnianej). **Nie wyłączamy** —
to ochrona przed DNS-rebinding.

Bez tego kroku wszystkie wdrożenia poza jednym dostaną 421 i nikt nie będzie
wiedział dlaczego.

---

## 7. Bezpieczeństwo

### 7.1 Przekazujemy WYŁĄCZNIE `Bearer`

Allowlista nagłówków wewnętrznego żądania: **`Authorization` tylko gdy schemat
to `Bearer`**, plus `Accept`. Odcinamy jawnie `Cookie`, `X-Forwarded-*`,
`Referer` i wszystko inne.

Dwa niezależne obejścia, gdyby przekazywać hurtem:

- **`Cookie`** → `SessionAuthentication` (`base.py:1058`) uwierzytelnia sesją.
  Pełne uprawnienia zalogowanego, bez zgody, bez scope, bez revoke. CSRF nie
  chroni, bo wykonujemy GET.
- **`Authorization: Basic`** → `BasicAuthentication` (`base.py:1059`)
  uwierzytelnia hasłem. Do tego `ApiReadOnlyForBearerMiddleware` sprawdza
  **wyłącznie prefiks `bearer `** (`middleware.py:33`), więc dla Basica druga
  warstwa read-only **nie istnieje**.

Oba wymagają testu regresyjnego.

### 7.2 Propagacja `Host` — to jest kontrola dostępu, nie kosmetyka

Wewnętrzne żądanie **musi** nieść `Host` zewnętrznego. Inaczej `Uczelnia=None`,
a wtedy (§2.5):

- `BramkaApiV1` **przepuszcza bezwarunkowo** — obejście wszystkich sześciu
  przełączników, w tym `api_v1_wlaczone` i `api_v1_tylko_zalogowani`. API
  wyłączone przez administratora staje się dostępne przez `/mcp`.
- `ukryte_statusy` → `None` → wyciekają rekordy ukrytych statusów korekty.
- W instalacji wielouczelnianej: nie wiadomo, czyje dane zwrócić.

Test wielo-hostowy obowiązkowy.

### 7.3 Throttling nie może zapaść się do jednego kubełka

`ASGITransport` ustawia `client=("127.0.0.1", 123)`. `SearchAnonThrottle` liczy
po IP → **wszyscy anonimowi użytkownicy MCP dzieliliby jeden limit**, czyli
jeden klient DoS-uje wszystkich. Dyspozytor wstawia do wewnętrznego scope'u
`client` = IP rozstrzygnięte z zewnętrznego żądania.

IP bierzemy przez istniejące `django_bpp.client_ip.get_client_ip` (używa go już
`views_dcr.py`), **nie** przez ślepe przepisanie `X-Forwarded-For`.

Osobno: strefa nginx `bpp_api` (60 r/s) **jest omijana** — wewnętrzne żądania
nie przechodzą przez nginx, a jedno wywołanie `pobierz_rekord` rozwija się na
N żądań API. Kierunek ryzyka jest odwrotny do tego, co pisała pierwsza wersja
specu (obawa o zbyt ciasny limit); realnie limit **nie działa** na tej ścieżce.

### 7.4 Rekurencja

`ASGITransport` dostaje `django_asgi_app`, nie `application`. Dodatkowo
`BppClientInProcess` odrzuca ścieżki spoza `/api/v1/`.

### 7.5 Widoczność

Wewnętrzne żądania nie trafiają do access-logu nginx ani uvicorna — ruch API
generowany przez MCP jest **niewidoczny dla dotychczasowego monitoringu**.
Logujemy je po stronie `KontekstMcpMiddleware` (ścieżka, kod, czas, obecność
bearera — **nigdy sam token**).

---

## 8. Strona `/mcp/` dla człowieka

`GET /mcp/` (ze slashem) → widok Django z instrukcją podłączenia; `POST /mcp` →
protokół. Rozdzielenie po ścieżce, nie po metodzie (§5.1).

Treść wzorowana na `mcp.sentry.dev`: adres złącza jako główna treść, jedno
zdanie o dostępie, gotowe wklejki dla klientów, link do `bpp-mcp` dla stdio.
Adres składany przez `build_absolute_uri` — każda uczelnia widzi swój.
Szablon podlega `LocaleMiddleware`, więc teksty przez `gettext`.

---

## 9. Zależności i obraz

Dochodzą do `pyproject.toml`:

```
bpp-mcp>=0.4,<0.5      # narzędzia + szwy
```

co ciągnie `mcp>=2,<3`, `httpx` i `starlette`. **Żadnego z nich nie ma dziś
w `uv.lock` BPP.** Konsekwencje do sprawdzenia przed scaleniem:

- rozmiar obrazu produkcyjnego,
- bramka Trivy w `build-docker-images.yml` (nowe pakiety = nowe CVE),
- czy `starlette` nie koliduje z wersją ciągniętą przez `channels[daphne]`.

---

## 10. Wdrożenie

Wbrew pierwszej wersji specu, **`bpp-deploy` wymaga zmian**:

1. **ModSecurity/CRS.** Wyłączenie obejmuje dziś tylko
   `^/(bpp|api/v1)/zapytanie/`. Ciało JSON-RPC na `/mcp` — zwłaszcza
   z zapytaniem DjangoQL w argumentach narzędzia — będzie skanowane przez CRS
   i 403 z WAF-a jest bardzo prawdopodobny. Potrzebne wyłączenie dla `/mcp`,
   zawężone jak istniejące.
2. **Strefa `limit_req`.** `/mcp` wpada dziś pod `location /` (100 r/s burst
   100). Do zmierzenia; jeśli agent się o to obija — własna strefa.

Bez zmian: `stateless_http` sprawia, że recykling `--max-requests` jest
nieszkodliwy i sticky sessions nie są potrzebne; `json_response` znosi problem
`proxy_read_timeout`.

---

## 11. Testy

Konwencja repo: pytest, bez `unittest.TestCase`, `model_bakery.baker`.

**Dyspozytor**
- scope `lifespan` → `startup.complete`; błąd startu → `startup.failed`
  (nie cisza)
- `POST /mcp` przed lifespanem → kontrolowany błąd, nie `RuntimeError`
- ruch spoza `/mcp` trafia do Django; `websocket` do channels
- `GET`/`DELETE` na `/mcp` trafiają do aplikacji MCP (nie do Django)

**Bezpieczeństwo (obowiązkowe, każdy osobno)**
- `Cookie` wysłany do `/mcp` **nie** uwierzytelnia (§7.1)
- `Authorization: Basic` **nie** jest przekazywany (§7.1)
- wewnętrzne żądanie niesie `Host` zewnętrznego; **test wielo-hostowy**:
  dwie `Uczelnia`, dwa hosty, każdy widzi swoje (§7.2)
- `api_v1_wlaczone=False` → `/mcp` też odmawia (dowód, że bramka działa)
- rekord o ukrytym statusie nie wycieka przez `/mcp`
- dwa różne IP → dwa kubełki throttlingu (§7.3)
- ścieżka spoza `/api/v1/` odrzucona (§7.4)

**Klient**
- `BppClientInProcess` zwraca to samo, co żądanie sieciowe dla tej ścieżki
- cache izolowany między żądaniami (dwa żądania, różne konteksty)
- wyjątek aplikacji → `BppNetworkError`, nie surowy traceback

**Protokół**
- `initialize` → `tools/list` → `tools/call` na żywej aplikacji, bez sieci
- 11 narzędzi + 1 prompt widoczne

**Ręcznie, do odnotowania w planie**
- podłączenie prawdziwego klienta Claude i pełny taniec OAuth

---

## 12. Kryteria akceptacji

- `POST /mcp` odpowiada na `initialize`, `tools/list`, `tools/call` bez tokenu,
  zwracając dane publiczne identyczne z `/api/v1/`.
- Ważny bearer → narzędzie widzi tożsamość użytkownika.
- Nieważny bearer → **401** z `WWW-Authenticate` wskazującym PRM.
- `Cookie` i `Basic` wysłane do `/mcp` **nie** uwierzytelniają.
- Dwie uczelnie na dwóch hostach widzą **swoje** dane; `api_v1_wlaczone=False`
  blokuje również `/mcp`.
- `/.well-known/oauth-protected-resource` poprawne przy wielu hostach.
- `GET /mcp/` renderuje stronę z adresem właściwym dla hosta.
- Narzędzia pochodzą z `bpp_mcp` — **żadnej kopii** w `src/`.
- `stateless_http=True`, `json_response=True`, brak długożyjących strumieni.
- Testy zielone; `ruff` czysty; `pre-commit` bez uwag.
- Newsfragment w `src/bpp/newsfragments/`.
- Istniejące testy `oauth_mcp` i `api_v1` przechodzą **bez modyfikacji**.

---

## 13. Poza zakresem

- Narzędzia mutujące (zapis przez MCP).
- **Rozszerzenie allowlisty DCR** o ChatGPT/Cursor — osobna decyzja
  bezpieczeństwa (§1.1).
- Konsolidacja reguł tokenu w `oauth_mcp/tokens.py` — projekt 3 (§3).
- WebMCP jako API przeglądarki (`navigator.modelContext`).
- Wygaszenie `bpp-mcp`.
- Zasoby (`resources`) MCP. Prompt `zloz_zapytanie_djangoql` wchodzi, bo
  `register_tools` rejestruje go razem z narzędziami — pierwsza wersja specu
  wykluczała prompty i jednocześnie wymagała braku kopii, co było sprzeczne.
- Własna strefa `limit_req` — dopiero po pomiarze (§10).
- RFC 8707 / audience binding — dziedziczone odstępstwo.

---

## 14. Czym ta wersja różni się od pierwszej

| Ustalenie recenzji | Werdykt po weryfikacji |
|---|---|
| Bloker: lifespan menedżera sesji | **potwierdzony** [probe], ale rozwiązywalny dyspozytorem (§5.1) — nie wymaga przeprojektowania |
| Bloker: host `bpp.invalid` | **potwierdzony i groźniejszy, niż zgłoszono** — to obejście kontroli dostępu, nie tylko 400 (§7.2) |
| `Cookie` → `SessionAuthentication` | potwierdzony; **dodatkowo `Basic`**, którego pierwsza wersja nie widziała (§7.1) |
| Cache współdzielony | potwierdzony; rozwiązany szwem z `bpp-mcp` 0.4.0 (§5.3) |
| Throttling w jednym kubełku | potwierdzony; kierunek ryzyka w pierwszej wersji był **odwrotny** (§7.3) |
| ModSecurity | potwierdzony — `bpp-deploy` jednak wymaga zmian (§10) |
| Allowlista DCR | potwierdzona — obietnica zasięgu była nieprawdziwa (§1.1) |
| 7 narzędzi z `tools.py` | **błąd** — 11 narzędzi + prompt, wrappery z `server.py` (§2.2) |
| Zakres | rozbity na trzy projekty (§3) |

Nowe, spoza recenzji — z probe'ów: `stateless_http`/`json_response` przeniesione
do `streamable_http_app()`, `json_response` znoszące SSE, oraz **własna
allowlista hostów aplikacji MCP** (§6.3), o której nie wiedziała ani pierwsza
wersja specu, ani recenzja.

---

## 15. Otwarte kwestie do rozstrzygnięcia w planie

1. **Czy klienci MCP odpalają OAuth przy 401 na kolejnym żądaniu, czy tylko
   przy `initialize`?** Jeśli tylko przy `initialize`, endpoint anonimowy nigdy
   nie zaproponuje logowania i potrzebny jest drugi adres (np. `/mcp/auth`).
   **Do weryfikacji empirycznej na żywym kliencie.** Częściowo łagodzi to
   istniejąca hybrydowa podpowiedź w treści odpowiedzi narzędzi.
2. Czy `starlette` z `bpp-mcp` koliduje z wersją z `channels[daphne]` (§9).
3. Wpływ nowych zależności na bramkę Trivy (§9).
4. Czy `limit_req` faktycznie boli (§10).
5. Kształt reguły wyłączającej ModSecurity dla `/mcp` (§10).
6. Czy `FirstRunWizardMiddleware` przekierowuje wewnętrzne `/api/v1/` na
   świeżej instalacji — niezweryfikowane bez uruchomienia.
7. Czy Rollbar scrubuje `Authorization` dla wyjątków z wewnętrznego scope'u.
