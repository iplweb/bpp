# Handoff: nauczyć skill `bpp-api` i serwer `bpp-mcp` endpointów `/api/v1/zapytanie/`

**Data:** 2026-07-11
**Kontekst:** PR #527 (feat-api-zapytanie) + `b7ea0eb59` (blocklist PII) na `dev`.
**Cel:** dopisać do skilla Claude (`bpp-api`) i serwera MCP (`bpp-mcp`) obsługę
**autoryzowanego** wyszukiwania DjangoQL po API — trzech nowych endpointów.

---

## 1. Co powstało (fakty z kodu)

Trzy read-only endpointy DRF (`src/api_v1/viewsets/zapytanie.py`,
`src/api_v1/serializers/zapytanie.py`, router w `src/api_v1/urls.py`):

```
GET /api/v1/zapytanie/rekord/?q=<djangoql>&limit=&offset=
GET /api/v1/zapytanie/autor/?q=<djangoql>&limit=&offset=
GET /api/v1/zapytanie/autorzy/?q=<djangoql>&limit=&offset=
```

- **Silnik:** `djangoql.queryset.apply_search(qs, q, schema=RekordLLMSchema).distinct()`.
- **Read-only:** tylko `GET` (router generuje wyłącznie `list`). POST/PUT/... → 405.
- **Paginacja:** LimitOffset, `PAGE_SIZE=10`, **twardy cap `limit=100`**.
- **Puste `q`** → `200 {"results": []}` (nie błąd).

### Różnica względem Fazy 0 (`/api/v1/szukaj/`)

| | `/szukaj/` (Faza 0) | `/zapytanie/*` (to) |
|---|---|---|
| Dostęp | anonimowy | **autoryzowany** (gate niżej) |
| Zapytanie | FTS `q=` (websearch) | pełny **DjangoQL** (pola/relacje/operatory) |
| Modele | wszystkie publikacje naraz | **osobno** Rekord / Autor / Autorzy |

## 2. Uwierzytelnianie (KLUCZOWE dla skilla i MCP)

Globalny `DEFAULT_AUTHENTICATION_CLASSES` (już aktywny dla całego `/api/v1/`):
`StrictOAuth2Authentication`, `SessionAuthentication`, `BasicAuthentication`.

- **Bearer MCP:** `Authorization: Bearer <token>`. Token wydaje AS BPP pod `/o/`
  (OAuth 2.1 + PKCE, z gałęzi feat-mcp-oauth). Zły/wygasły bearer → **401**
  (`StrictOAuth2Authentication` NIE degraduje po cichu do anonima).
- **Sesja:** cookie zalogowanego użytkownika (dla web/curl z cookie jar).
- **Gate (permission):** `MoznaUzywacZapytania` → `user_can_use_query_editor`:
  **superuser ALBO staff w grupie „wprowadzanie danych"**. User NIE spełniający
  gate (także zwykły zalogowany) → **403**. Bearer działa tylko, gdy jego user
  spełnia gate.
- **Preflight tożsamości:** `GET /api/v1/whoami/` (z feat-mcp-oauth) — sprawdź,
  kim jest token, zanim odpalisz zapytania.

## 3. Kształt odpowiedzi (kompaktowe, płaskie — bez chodzenia po hyperlinkach)

### `/zapytanie/rekord/` — reuse `SzukajSerializer` (spójne z Fazą 0)
```json
{
  "id": "<content_type_id>-<pk>",
  "tytul_oryginalny": "…",
  "rok": 2024,
  "opis_bibliograficzny": "…",
  "rekord_url": "https://host/api/v1/wydawnictwo_ciagle/123/?format=json",
  "absolute_url": "https://host/bpp/rekord/…"
}
```

### `/zapytanie/autor/` — `AutorKompaktSerializer`
```json
{
  "id": 42, "slug": "jan-kowalski", "nazwisko": "Kowalski", "imiona": "Jan",
  "tytul": "prof.", "orcid": "0000-…",
  "aktualna_jednostka": "Katedra Kardiologii",
  "autor_url": "https://host/api/v1/autor/42/",
  "absolute_url": "https://host/bpp/autor/…"
}
```

### `/zapytanie/autorzy/` — `AutorzyKompaktSerializer` (wpis autorstwa)
```json
{
  "id": "<ct>-<pk>", "zapisany_jako": "J. Kowalski", "kolejnosc": 1,
  "autor_url": "https://host/api/v1/autor/42/",
  "rekord": {"tytul": "…", "rekord_url": "https://host/api/v1/…/123/"},
  "typ_odpowiedzialnosci": "aut.", "jednostka": "Katedra…", "dyscyplina": "…"
}
```

Odpowiedź opakowana w standardową kopertę LimitOffset:
`{"count", "next", "previous", "results": [...]}`.

## 4. Język zapytań: co jest ODPYTYWALNE (schemat = `RekordLLMSchema`)

Schemat walidacji to `bpp.djangoql_schema.RekordLLMSchema` (allow-lista
`SEARCH_ALLOWLIST`, bez pickerów `<fk>__rel`). **Źródło prawdy dla korzenia
Rekord:** commitowany artefakt `src/bpp/data/rekord_djangoql_schema.compact.txt`
(regenerowany komendą `opisz_schemat_djangoql_dla_llm`). To jest DOKŁADNIE ten
sam schemat, wg którego walidowane są zapytania → round-trip.

### Przykładowe zapytania (poprawne)
```
# rekord:
rok >= 2022 and punkty_kbn >= 100
charakter_formalny.skrot = "AC" and jezyk.skrot = "pol"
autorzy.autor.nazwisko = "Kowalski" and rok = 2023
zrodlo.nazwa ~ "Nature" and impact_factor > 5
# autor:
nazwisko ~ "Kowal" and tytul.skrot = "prof."
aktualna_jednostka.nazwa ~ "Kardiolog" and orcid != ""
# autorzy:
rekord.rok = 2023 and typ_odpowiedzialnosci.skrot = "aut."
```

### Pułapki dla skilla/MCP (uczyć agenta)
- **Round-trip pełny TYLKO dla Rekord.** Compact-schemat generujemy dziś tylko
  z korzenia Rekord. `/zapytanie/autor/` i `/zapytanie/autorzy/` DZIAŁAJĄ, ale
  agent nie ma „nauczonego" opisu ich pól. Kluczowe pola: patrz §5. (Follow-up:
  rozszerzyć `opisz_schemat_djangoql_dla_llm` o korzenie Autor/Autorzy.)
- **Błąd składni/pola → HTTP 400** z `{"error", "line", "column", "mark"}` —
  agent powinien to sparsować i poprawić zapytanie (pozycja błędu w `q`).
- **Za wolne zapytanie → HTTP 503** (`statement_timeout` 8 s) — zawęź warunki.
- **`?format=json`** albo nagłówek `Accept: application/json` (inaczej HTML
  browsable API).
- **Cap `limit=100`** — pełny harvest = stronicowanie offsetem.

## 5. Bezpieczeństwo: co NIE przechodzi (po `b7ea0eb59`)

Ważne: DjangoQL pozwala FILTROWAĆ po każdym polu schematu — nawet niezwracanym
w odpowiedzi (atak-wyrocznia przez `~`/`=`/`startswith`). Dlatego schemat
agent-facing jest węższy niż web-edytor:

- **Ukryte (blocklist w `RekordLLMSchema`, nieodpytywalne):**
  `autor.email`, `autor.adnotacje`, `autor.opis`, `jednostka.email`,
  `rekord.adnotacje` (+ podtypy publikacji). Zapytanie po nich → 400.
- **Niedostępne z natury:** `pesel` (nie istnieje na modelu), hasła/tokeny
  uczelni (`Uczelnia` docięta do `nazwa`/`skrot`), konta `BppUser` (poza
  allow-listą), surowy JSON PBN `versions` (typ nieodpytywalny).
- **Świadomie ZOSTAJĄ odpytywalne (decyzja właściciela):**
  `autor.system_kadrowy_id`, `autor.poprzednie_nazwiska`,
  `autor.pbn_uid.pbnId/polonUid/qualifications` (trawersacja do
  `pbn_api.scientist`).

## 6. Konkretne zadania — skill `bpp-api`

Dopisać do `SKILL.md` (sekcja DjangoQL, którą skill już wzmiankuje ogólnie):

1. **Nowa sekcja „Precyzyjne zapytania (DjangoQL) — dla zalogowanych".**
   - Endpointy §1, auth §2 (bearer/sesja + gate staff/superuser), `whoami`
     preflight.
   - Że to inne niż anonimowy `/szukaj/`: wymaga tokenu/sesji, zwraca 401/403
     bez uprawnień.
2. **Kształty odpowiedzi §3** (per model) + koperta LimitOffset.
3. **Ściągawka języka §4** + link, że pełny schemat pól Rekord jest w
   `rekord_djangoql_schema.compact.txt` (dołączyć skrót jako `references/`),
   i uczciwie: dla Autor/Autorzy podać listę pól z §5 (bo brak compact-schematu).
4. **Obsługa błędów:** 400 z pozycją, 503 timeout, 100-cap, `?format=json`.
5. **Recepty curl** (przykłady §7).
6. Trigger skilla: dodać frazy „zapytanie DjangoQL po API", „precyzyjne
   wyszukiwanie rekordów/autorów zalogowanym", „bpp zapytanie autor/rekord".

## 7. Konkretne zadania — serwer `bpp-mcp`

Dodać trzy narzędzia (FastMCP), analogicznie do istniejących:

| Narzędzie | Endpoint | Rola |
|---|---|---|
| `zapytanie_rekord(q, limit?, offset?)` | `/zapytanie/rekord/` | DjangoQL po publikacjach |
| `zapytanie_autor(q, limit?, offset?)` | `/zapytanie/autor/` | DjangoQL po autorach |
| `zapytanie_autorzy(q, limit?, offset?)` | `/zapytanie/autorzy/` | DjangoQL po wpisach autorstwa |

Wymagania implementacyjne:
- **Auth bearer:** klient `httpx` z nagłówkiem `Authorization: Bearer <token>`
  (token z OAuth flow `/o/`; konfiguracja jak `BPP_BASE_URL` — dołożyć
  `BPP_OAUTH_*`). Bez tokenu spełniającego gate → 401/403 (mapować na czytelny
  komunikat, nie traceback).
- **`Accept: application/json`**, auto-follow paginacji LimitOffset do `limit`.
- **Mapowanie błędów:** 400 → zwróć `{error, line, column}` agentowi jako
  „popraw zapytanie" (z pozycją); 503 → „zawęź zapytanie"; 401 → „token
  nieważny/niewystarczające uprawnienia".
- **Opis narzędzia = ściągawka DjangoQL** (§4) — zwłaszcza dla Rekord dołączyć
  skrót compact-schematu; dla Autor/Autorzy listę pól (§5) do czasu follow-upu.
- Testy respx: happy path per narzędzie, 400 (złe pole), 401 (zły token),
  pusty wynik, paginacja wielostronicowa.

## 8. Otwarte follow-upy (świadome)

- **Compact-schemat dla Autor/Autorzy** — rozszerzyć
  `opisz_schemat_djangoql_dla_llm` o te korzenie, żeby round-trip agenta był
  pełny (dziś tylko Rekord). Do czasu — skill/MCP opisują pola ręcznie (§5).
- **Trawersacja do `pbn_api.*`** jest osiągalna mimo `include=SEARCH_ALLOWLIST`
  (allow-lista gate'uje korzenie, nie cele trawersu FK). Właściciel świadomie
  zostawił `pbn_uid`/`polonUid`. Gdyby trzeba zamknąć — potrzebny realny
  cut FK do modeli spoza allow-listy w schemacie.
- **Throttling** — dziś brak (reszta `api_v1` też nie throttluje). DjangoQL jest
  droższy; rozważyć `ScopedRateThrottle`, zwłaszcza że bearer/MCP automatyzuje.
- **Multi-uczelnia** — `/zapytanie/rekord/` NIE zawęża per uczelnia (narzędzie
  redakcyjne, staff), w odróżnieniu od anonimowego `/szukaj/`.

## 9. Wskazówki do weryfikacji end-to-end

- Podnieś stack: `uv run run-site run` (lub dump prawdziwej bazy). Zaloguj się
  jako superuser/staff-w-grupie.
- `curl` z cookie jar (autologin dev-helpers) LUB z tokenem bearer po flow `/o/`.
- Smoke: `?q=rok=2024&format=json` na każdym z 3 endpointów; sprawdź 400 na
  `?q=nieistniejace_pole=1`; sprawdź 403 dla usera spoza gate.
