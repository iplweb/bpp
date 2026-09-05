# Hostowany serwer MCP w serwisie BPP (`/mcp`)

Data: 2026-09-05
Status: projekt do zatwierdzenia
Poprzednik: `2026-07-11-mcp-oauth-authorization-design.md` (Faza 3 — warstwa
OAuth po stronie BPP; **zrealizowana**, `src/oauth_mcp/`)

---

## 1. Cel i motywacja

Dziś dostęp AI do danych BPP idzie przez `bpp-mcp` — pakiet z PyPI, który
użytkownik instaluje do swojego klienta MCP jako serwer stdio. Model działa,
ale ma trzy koszty:

1. **Próg wejścia.** Użytkownik potrzebuje Pythona i `uvx`, a przede wszystkim
   musi **znać i wpisać adres swojej instancji** (`BPP_BASE_URL` celowo nie ma
   wartości domyślnej — każde wdrożenie to inna uczelnia).
2. **Odcięta kategoria klientów.** Klienci webowi (claude.ai, chatgpt.com) i
   urządzenia mobilne **nie mają jak uruchomić procesu lokalnego**. Dla
   użytkownika nietechnicznego przeglądarka bywa jedynym kontaktem z asystentem.
3. **Skos wersji.** N wersji pakietu × M wdrożeń BPP. Widać to już w kodzie:
   `bpp_mcp.oauth_client.AuthMode` ma warianty `PASSTHROUGH`/`PROXY`, żeby
   obsłużyć instancje z warstwą OAuth i bez niej, a `_konwencjonalne()` trzyma
   hardkodowane ścieżki `/o/*` jako fallback. Każda zmiana w `/api/v1/` tę
   gałąź rozbudowuje.

**Cel:** BPP wystawia własny endpoint MCP pod `/mcp`, wyjeżdżający z tym samym
obrazem dockerowym co reszta serwisu. Użytkownik wkleja do klienta AI adres
swojej instancji z dopiskiem `/mcp` i to jest cała konfiguracja.

**Nie-cel:** wygaszenie `bpp-mcp`. Pakiet zostaje dla trybu stdio i dla
wskazywania instancji deweloperskich; przestaje być ścieżką rekomendowaną
w pierwszej kolejności.

---

## 2. Kontekst — rzeczywistość ustalona z kodu

Ustalenia z lektury, nie z pamięci. Numery linii wg stanu na `dev` @ `31d3d4612`.

### 2.1 Strona BPP — warstwa OAuth istnieje i jest kompletna

`src/oauth_mcp/` realizuje pełny Authorization Server:

| Element | Plik |
|---|---|
| `/o/authorize/`, `/o/token/`, `/o/revoke_token/` (DOT, cherry-pick) | `urls.py` |
| DCR `/o/register/` (RFC 7591) + allowlista redirect_uri + rate-limit | `views_dcr.py` |
| AS metadata `/.well-known/oauth-authorization-server` (RFC 8414) | `views_metadata.py` |
| `StrictOAuth2Authentication` — bearer → `request.user`, twarde 401 | `authentication.py` |
| `ApiReadOnlyForBearerMiddleware` — mutacje `/api/v1/` bearerem → 403 | `middleware.py` |
| `/api/v1/whoami/` — preflight tożsamości | `views_whoami.py` |
| revoke przy zmianie hasła / dezaktywacji | `signals.py` |
| sprzątanie osieroconych rejestracji DCR (celery, 1:45) | `tasks.py` |

`StrictOAuth2Authentication` jest **pierwszą** klasą w
`REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]` (`base.py:1056`), przed
`SessionAuthentication` i `BasicAuthentication`.

### 2.2 Strona `bpp-mcp` — szew wstrzykiwania już istnieje

- Siedem narzędzi w `bpp_mcp/tools.py`; **każde przyjmuje `client: BppClient`
  jako pierwszy argument**.
- `BppClient` (`client.py`) ma dokładnie dwie metody dostępu do danych:
  `get_json()` i `get_paginated()`. Reszta klasy — budowanie URL-i, biała lista
  cache'owalnych prefiksów, auto-follow paginacji, mapowanie 404 →
  `BppNotFound` — jest **niezależna od transportu**.
- `httpx.AsyncClient` jest konstruowany **na sztywno** w `BppClient.__init__`
  (bez parametru `transport`). To jedyna przeszkoda techniczna.
- Tryb HTTP już istnieje: `server.py` obsługuje `--http` →
  `run(transport="streamable-http")` z `AuthSettings` i `WhoamiTokenVerifier`.

### 2.3 Infrastruktura

- ASGI: `src/django_bpp/asgi.py` — `ProtocolTypeRouter` z
  `{"http": django_asgi_app, "websocket": ...}`.
- Produkcja: `gunicorn django_bpp.asgi:application` z `UvicornWorker`
  i **recyklingiem `--max-requests`** (`docker/appserver/entrypoint-appserver.sh:104`).
- nginx (`bpp-deploy`): `proxy_*_timeout` 60/300/300 s, strefy `limit_req`
  na `location /`.
- `api_v1.pagination.BppLimitOffsetPagination` **ma** twardy `max_limit`
  (`base.py:1053`).

---

## 3. Decyzje architektoniczne

| # | Decyzja | Uzasadnienie |
|---|---|---|
| D1 | Kierunek zależności: **BPP zależy od `bpp-mcp`** | Jedna implementacja narzędzi, zero rozjazdu. Wybór użytkownika. |
| D2 | Montaż: **dyspozytor w `asgi.py`** (wariant A) | Punkt wpięcia istnieje; zero zmian w `bpp-deploy`. |
| D3 | **`stateless_http=True`** | Wymuszone przez recykling workera gunicorna — stateful sesja ginie z procesem w środku pracy użytkownika. |
| D4 | Dostęp do danych: **`httpx.ASGITransport`** na `django_asgi_app` | Ta sama ścieżka kodu co przez sieć, bez gniazda. `BppClient` bez zmian. |
| D5 | Polityka dostępu: **dziedziczona z `/api/v1/`** | Anonimowo do odczytu, bearer odblokowuje resztę. Nie wprowadzamy nowej polityki. |
| D6 | **Read-only** w pierwszej wersji | Zgodnie z `middleware.py`; narzędzia mutujące poza zakresem. |

### 3.1 Dlaczego `ASGITransport`, a nie `resolve()` + syntetyczny request

Rozważany był wariant „nadpisz `BppClient._request`, rozwiąż URL w URLconfie,
zbuduj syntetyczny request, zawołaj widok DRF". Odrzucony na rzecz D4:

| | `resolve()` + syntetyczny request | `ASGITransport` |
|---|---|---|
| Zmiany w `BppClient` | nadpisanie `_request` | **żadne** poza szwem `transport=` |
| Middleware Django | **nie biegnie** | biegnie w całości |
| Most sync↔async | do rozwiązania po naszej stronie | **robi handler ASGI Django** |
| „ta sama ścieżka kodu" | w przybliżeniu | dosłownie |

Wzorzec jest ustalony w ekosystemie: `fastapi-mcp` używa `ASGITransport`
**domyślnie** — komunikuje się z aplikacją bez żądań HTTP, nie wymaga
`base_url`, a serwer nie musi nawet działać.

---

## 4. Architektura

```
                        gunicorn + UvicornWorker
                                 │
                   django_bpp.asgi:application
                                 │
                    ┌────────────┴────────────┐
              ścieżka /mcp*              wszystko inne
                    │                          │
          aplikacja FastMCP              django_asgi_app
       (stateless streamable HTTP)              ▲
                    │                           │
              narzędzia z bpp_mcp.tools         │
                    │                           │
            BppClient(transport=ASGITransport(──┘)
```

Klucz: `ASGITransport` dostaje **`django_asgi_app`**, nie `application`.
`application` to `ProtocolTypeRouter` zawierający routing na `/mcp` —
podanie go groziłoby rekurencją.

### 4.1 Nowa aplikacja Django: `src/mcp_server/`

Zgodnie z konwencją repo (aplikacja per obszar funkcjonalny):

```
src/mcp_server/
    __init__.py
    apps.py
    asgi_app.py        # budowa aplikacji FastMCP + montaż narzędzi
    client.py          # BppClientInProcess (podklasa z bpp_mcp)
    auth.py            # rozstrzyganie bearera na wejściu /mcp
    views.py           # strona /mcp/ dla człowieka (HTML)
    urls.py            # /mcp/ (HTML) — endpoint protokołu jest w asgi.py
    templates/mcp_server/index.html
    tests/
```

Warstwa OAuth **zostaje w `oauth_mcp`** — `mcp_server` z niej korzysta,
nie duplikuje. Nowy widok RFC 9728 trafia do `oauth_mcp/views_metadata.py`,
obok istniejącego RFC 8414 (patrz §6.1).

---

## 5. Dostęp do danych — `BppClientInProcess`

```python
# src/mcp_server/client.py
import httpx
from bpp_mcp.client import BppClient
from django_bpp.asgi import django_asgi_app


class BppClientInProcess(BppClient):
    """BppClient wołający własną aplikację Django bez gniazda TCP."""

    def __init__(self, config, **kwargs):
        super().__init__(
            config,
            transport=httpx.ASGITransport(app=django_asgi_app),
            **kwargs,
        )
```

Odziedziczona mechanika — co żyje, a co umiera:

| Element `BppClient` | W procesie |
|---|---|
| retry ×2 + backoff | **martwy** — brak sieci do ponowienia; `max_retries=0` |
| semafor współbieżności (8) | **zostaje** — dławi równoległą pracę bazy |
| cache prefiksów słownikowych | **zostaje** bez zmian |
| auto-follow paginacji | **zostaje** — `next` z DRF jest bezwzględny, `_full_url` to obsługuje |
| mapowanie błędów (404 → `BppNotFound`) | **zostaje** — te same kody statusu |

`config.api_root` wskazuje na `http://<dowolny-host>/api/v1` — host jest
nieużywany przy `ASGITransport`, ale musi być syntaktycznie poprawny, bo
`httpx` buduje z niego `URL`. Ustalamy `http://bpp.invalid/api/v1`, żeby
przypadkowe wyjście do sieci **nie mogło się udać po cichu**.

### 5.1 Zmiana wymagana w `bpp-mcp` (drugie repo)

`BppClient.__init__` musi przyjąć opcjonalny `transport` i przekazać go do
`httpx.AsyncClient`. Jedna linia sygnatury + jedna w konstruktorze; domyślne
zachowanie (`transport=None`) bez zmian, więc niekompatybilności nie ma.

Wymaga wydania `bpp-mcp` przed wydaniem BPP. Kolejność w planie:
PR w `bpp-mcp` → release na PyPI → pin w `pyproject.toml` BPP.

---

## 6. Uwierzytelnianie i polityka dostępu

### 6.1 Przepływ na wejściu `/mcp`

```
brak nagłówka Authorization  → przepuść bez niego → AnonymousUser
                                → dane publiczne (polityka /api/v1/)
ważny bearer                 → przepuść nagłówek dalej
                                → DRF ustala tożsamość StrictOAuth2Authentication
nieważny / wygasły / bez scope → 401 + WWW-Authenticate
```

Nagłówek `WWW-Authenticate` przy 401:

```
Bearer resource_metadata="https://<host>/.well-known/oauth-protected-resource"
```

Nowy widok w `oauth_mcp/views_metadata.py` (RFC 9728), bliźniak istniejącego
RFC 8414 — ten sam wzorzec `build_absolute_uri` dla wielo-domenowości:

```json
{
  "resource": "https://<host>/mcp",
  "authorization_servers": ["https://<host>"],
  "scopes_supported": ["read"],
  "bearer_methods_supported": ["header"]
}
```

Spec z 2026-07-11 §6 przypisywał ten plik pakietowi `bpp-mcp`. **Przenosi się
do BPP** — Resource Serverem jest teraz instancja.

### 6.2 Jedno źródło prawdy o ważności tokenu

Reguły „co znaczy ważny token MCP" żyją dziś w dwóch miejscach:

- `authentication.py` — `is_active` + wymagany scope `read` + twarde 401,
- `middleware.py::_ma_wazny_bearer` — `AccessToken.is_valid()`.

Warstwa MCP byłaby trzecim. **Wyciągamy je do `oauth_mcp/tokens.py`**
i konsumujemy w trzech miejscach. To nie refaktor na boku — bez tego
„ważny token" znaczy trzy różne rzeczy, a rozjazd jest kwestią czasu.

Sygnatura:

```python
def zweryfikuj_bearer(raw: str) -> tuple[User, AccessToken]:
    """Podnosi BearerNiewazny gdy token nie istnieje, wygasł, konto jest
    nieaktywne albo brakuje scope 'read'."""
```

`StrictOAuth2Authentication` zachowuje integrację z DRF (dziedziczenie po
`OAuth2Authentication`), ale **reguły** po-sprawdzające deleguje do helpera.

### 6.3 Warstwa MCP dekoduje token wyłącznie dla kodu HTTP

Kuszące jest rozstrzygnąć token raz w warstwie MCP i podać widokowi gotowe
`request.user`. **Nie robimy tego** — powstałby drugi tor uwierzytelniania,
mogący rozjechać się ze `StrictOAuth2Authentication`, klasą o niebanalnych
regułach chronionych testami w `test_authentication.py`.

Przekazujemy **surowy nagłówek** do wewnętrznego żądania; DRF uwierzytelnia
normalnie, tą samą klasą. Warstwa MCP dekoduje token tylko po to, by
zdecydować między 401 transportu a przepuszczeniem.

### 6.4 `whoami` przestaje być potrzebne dla tej ścieżki

`bpp-mcp` robi round-trip do `/api/v1/whoami/`, bo token jest opaque, a pakiet
stoi po drugiej stronie sieci. Tutaj weryfikacja to lookup w tej samej bazie.
Znika `WhoamiUnavailable` i rozróżnianie „token nieważny (401)" od „BPP
nieosiągalne (500)". **Endpoint `whoami` zostaje** — używa go nadal `bpp-mcp`.

---

## 7. Bezpieczeństwo

### 7.1 Przekazujemy WYŁĄCZNIE `Authorization` — nigdy `Cookie`

`SessionAuthentication` jest w `DEFAULT_AUTHENTICATION_CLASSES`
(`base.py:1058`). Gdyby warstwa MCP przekazywała nagłówki hurtem, klient
wysyłający `Cookie:` do `/mcp` **uwierzytelniłby się sesją**, omijając cały
model OAuth — z pełnymi uprawnieniami zalogowanego użytkownika i bez zgody,
bez revoke, bez scope.

Allowlista nagłówków wewnętrznego żądania: `Authorization`, `Accept`.
Wszystko inne (`Cookie`, `X-Forwarded-*`, `Referer`) **odcinamy jawnie**.
Test regresyjny obowiązkowy.

### 7.2 Read-only

`ApiReadOnlyForBearerMiddleware` biegnie w wewnętrznym żądaniu (bo idzie ono
przez pełny stos Django) — czyli mutacja bearerem dostanie 403 tak samo jak
przez sieć. Niezależnie od tego narzędzia MCP wykonują **wyłącznie GET**.
Dwie warstwy, jak w spec §5.4 z 2026-07-11.

### 7.3 Rekurencja

`ASGITransport` dostaje `django_asgi_app`, nie `application`. Dodatkowo
zabezpieczenie: `BppClientInProcess` odrzuca ścieżki spoza `/api/v1/`.

### 7.4 Otwarte DCR na domenie produkcyjnej

Bez zmian względem stanu obecnego — `/o/register/` już jest publiczne, ma
rate-limit i sprzątanie osieroconych rejestracji. `/mcp` nie pogarsza sytuacji,
ale **zwiększa ruch na tej ścieżce**, więc rate-limit trzeba obserwować.

---

## 8. Discovery i strona dla człowieka

Pod `/mcp` mieszkają dwie rzeczy o różnych odbiorcach:

- **`POST /mcp`** — protokół MCP (JSON-RPC over streamable HTTP), obsługiwany
  przez aplikację FastMCP w `asgi.py`.
- **`GET /mcp/`** — strona HTML dla człowieka, widok Django w `mcp_server`.

Rozdzielenie po metodzie i ukośniku jest jednoznaczne: klienci MCP wołają
`POST` na `/mcp`, przeglądarka `GET` na `/mcp/`.

Treść strony (wzorzec: `mcp.sentry.dev`):

- adres złącza jako główna treść: `https://<host>/mcp`
- jedno zdanie o dostępie: publiczny odczyt bez logowania; token odblokowuje
  dane niepubliczne
- gotowe wklejki per klient: `claude mcp add`, JSON dla Cursora, kroki VS Code
- link do `bpp-mcp` dla trybu stdio

Strona korzysta z `request.build_absolute_uri`, więc każda uczelnia widzi
**swój** adres bez konfiguracji.

---

## 9. Wdrożenie

Nic do zrobienia w `bpp-deploy` — `/mcp` jedzie pod istniejącym
`location /`. Dwie rzeczy do obserwacji, nie do zmiany na wejściu:

1. **`limit_req` z `location /`** obejmie `/mcp`. Agent robiący kilkanaście
   wywołań narzędzi pod rząd może się o to obić. Do zmierzenia; jeśli boli —
   własna strefa w `_bpp-locations.conf`.
2. **Pula wątków workera.** Zewnętrzne żądanie `/mcp` trzyma worker, a
   wewnętrzne wywołania DRF idą do puli wątków tego samego procesu.
   Zakleszczenia nie ma (widoki DRF są synchroniczne, więc handler ASGI
   odsyła je do wątków), ale rozmiar puli przy równoległym rozwijaniu
   hyperlinków w `pobierz_rekord` **wymaga pomiaru**, nie założenia.

`stateless_http=True` sprawia, że recykling `--max-requests` jest nieszkodliwy
i że nie ma potrzeby sticky sessions. `proxy_read_timeout 300s` nie jest
problemem, bo nie utrzymujemy długich strumieni.

---

## 10. Testy

Poziomy, zgodnie z konwencją repo (pytest, bez `unittest.TestCase`,
`model_bakery.baker`):

**Jednostkowe (`src/mcp_server/tests/`)**
- `BppClientInProcess` zwraca dla `/api/v1/publikacje/` to samo, co klient
  sieciowy dla tej samej ścieżki (test na `ASGITransport`, `@pytest.mark.django_db`)
- allowlista nagłówków: `Cookie` przekazany do `/mcp` **nie** uwierzytelnia
  (§7.1) — test regresyjny
- ścieżka spoza `/api/v1/` odrzucona (§7.3)
- anonim dostaje dane publiczne; nieważny bearer → 401 + `WWW-Authenticate`
- ważny bearer → tożsamość z `request.user` w wewnętrznym żądaniu

**`oauth_mcp`**
- `oauth-protected-resource` zwraca poprawne URL-e przy różnych hostach
  (wielo-domenowość, jak istniejący `test_metadata.py`)
- `zweryfikuj_bearer` — parytet z dotychczasowym zachowaniem
  `StrictOAuth2Authentication` i `_ma_wazny_bearer` (testy istniejące muszą
  przejść bez zmian)

**Protokół**
- `initialize` → `tools/list` → `tools/call` na żywej aplikacji ASGI
  (klient MCP z SDK, bez sieci)

**Ręcznie, do odnotowania w planie**
- podłączenie prawdziwego klienta (Claude) i przejście tańca OAuth end-to-end

---

## 11. Poza zakresem

- Narzędzia mutujące (zapis/import przez MCP).
- WebMCP jako API przeglądarki (`navigator.modelContext`) — osobny projekt.
- Wygaszenie `bpp-mcp`.
- Zasoby (`resources`) i prompty MCP — tylko `tools` w pierwszej wersji.
- Własna strefa `limit_req` w nginksie (dopiero po pomiarze, §9).
- RFC 8707 / audience binding — dziedziczone odstępstwo z poprzedniego specu.

---

## 12. Otwarte kwestie do rozstrzygnięcia w planie

1. **Czy klienci MCP odpalają OAuth przy 401 na kolejnym żądaniu, czy tylko
   przy `initialize`?** Jeśli tylko przy `initialize`, endpoint anonimowy nigdy
   nie zaproponuje logowania i potrzebny jest drugi adres (np. `/mcp/auth`) dla
   pełnego dostępu. **Do weryfikacji empirycznej na żywym kliencie**, nie z
   lektury specyfikacji. Częściowo łagodzi to istniejący mechanizm hybrydowej
   podpowiedzi logowania w treści odpowiedzi narzędzi
   (`BppClient.transport` steruje nim dla DjangoQL).
2. Rozmiar puli wątków i zachowanie pod obciążeniem (§9.2).
3. Czy `limit_req` faktycznie boli (§9.1).
4. Wersja `bpp-mcp` do przypięcia po wydaniu szwu `transport=` (§5.1).
5. Czy `config.transport` w `BppClient` (dziś `"stdio"`/`"http"`) potrzebuje
   trzeciej wartości `"in-process"` — steruje hybrydową podpowiedzią logowania,
   która w tym trybie powinna brzmieć inaczej niż w stdio.
6. Stały komentarz w `bpp_mcp/client.py` twierdzi, że „BPP nie deklaruje
   `max_limit` po stronie DRF" — jest nieaktualny (`BppLimitOffsetPagination`
   ma twardy cap). Poprawić przy okazji PR-a w `bpp-mcp`.

---

## 13. Kryteria akceptacji

- `POST /mcp` odpowiada na `initialize`, `tools/list`, `tools/call` bez tokenu,
  zwracając dane publiczne identyczne z `/api/v1/`.
- Ważny bearer → wywołanie narzędzia widzi tożsamość użytkownika.
- Nieważny bearer → **401** z `WWW-Authenticate` wskazującym
  `oauth-protected-resource`.
- `Cookie` wysłany do `/mcp` **nie** uwierzytelnia (§7.1).
- `/.well-known/oauth-protected-resource` poprawne przy wielu hostach.
- `GET /mcp/` renderuje stronę z adresem złącza właściwym dla hosta.
- Narzędzia pochodzą z `bpp_mcp.tools` — **żadnej kopii** w `src/`.
- `stateless_http=True`; brak długożyjących strumieni.
- Testy zielone; `ruff format` + `ruff check` czyste; `pre-commit` bez uwag.
- Newsfragment w `src/bpp/newsfragments/`.
- Istniejące testy `oauth_mcp` przechodzą **bez modyfikacji**.
