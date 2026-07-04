# Wyszukiwanie „przez sztuczną inteligencję" — spec projektowy

Data: 2026-07-04
Status: zaakceptowany do implementacji (spec, po review Fable)

## Cel

Umożliwić odpytywanie bazy BPP zapytaniami w języku naturalnym (polskim).
Użytkownik wpisuje pytanie po polsku, model Claude tłumaczy je na zapytanie
DjangoQL, a wynik jest wykonywany i renderowany **tą samą maszynerią co
istniejące „szukaj zapytaniem"** (przez redirect).

Nowa pozycja w menu top-bar „szukaj": obecnie `precyzyjnie`, `szybko`,
`zapytaniem` → dochodzi **„przez sztuczną inteligencję"**.

## Zasada naczelna — front-end do istniejącego „zapytaniem"

To NIE jest nowy silnik zapytań. Ścieżka:

```
pytanie PL ──> Claude (SDK anthropic, Sonnet 5) ──> {"query": ..., "error": ...}
                                                        │
                                        walidacja DjangoQL (apply_search build)
                                                        │
    query poprawny ──> redirect: bpp:zapytanie?model=...&query=<DSL>
                         (render/paginacja/highlight = istniejący ZapytanieView.get)
    query BŁĘDNY składniowo ──> ZWRÓĆ do modelu z KONKRETNYM błędem:
                         „zapytanie <Q> zwróciło błąd DjangoQL: <komunikat>
                          w linii L, kolumnie C; skoryguj" ──> retry (bounded)
    query = null ──> pokaż error (pytanie niewyrażalne w DSL)
```

Konsekwencje tej zasady:

- **Bezpieczeństwo jest już rozwiązane.** DjangoQL `apply_search` robi wyłącznie
  filtrowanie read-only queryset-u. `Rekord` jest `managed = False`
  (widok/cache `bpp_rekord_mat`); `Autor` filtrujemy tylko po stronie odczytu.
  Wygenerowany string jest walidowany parserem DjangoQL **przed** redirectem.
  Najgorszy przypadek prompt-injection to drogie `count()`/`distinct()` na
  `bpp_rekord_mat` — a to jest już osiągalne z ręcznego „zapytaniem", więc
  **nie dokładamy nowej powierzchni ataku**. Pętla retry echu-je zepsuty query
  + błąd z powrotem do modelu — nieszkodliwe (najwyżej zmarnowane próby).
- **Reuse renderu przez redirect** (nie refaktor). `ZapytanieView.get()`
  (`src/bpp/views/zapytanie.py:401`) już renderuje wyniki z parametrów GET.
  Widok AI po udanym tłumaczeniu **przekierowuje na
  `bpp:zapytanie?model=...&query=...`** i dostaje render, paginację,
  `_attach_admin_urls`, highlight błędów oraz **edytowalny wygenerowany query**
  (escape hatch) za darmo, zero ryzyka refaktoru. Oryginalne pytanie PL
  przekazywane przez session flash (opcjonalnie mały baner w `zapytanie.html`).
- **Audytorium i schemat identyczne** jak „zapytaniem" — ten sam gate dostępu,
  ta sama `BppQLSchema`, te same modele (Rekord, Autor).

## Zakres iteracji 1

- Oba modele: **Rekord** i **Autor** (jak „zapytaniem", radio wyboru).
- Dostęp jak „zapytaniem": superuser **lub** staff w grupie
  „wprowadzanie danych" (`WprowadzanieDanychOrSuperuserMixin` /
  `user_can_use_query_editor`, `src/bpp/views/zapytanie.py:274-294`).
- Model: **`claude-sonnet-5`** przez oficjalny SDK `anthropic` (konfigurowalny).
- Kontrola kosztów: **budżety w PLN** (dzienny + miesięczny), twardy blok po
  przekroczeniu. Brak liczników liczby zapytań.
- Logowanie każdego zapytania wraz z kosztem (USD + PLN).

## Klient LLM — oficjalny SDK `anthropic` (nie LiteLLM)

Decyzja po review: **oficjalny SDK `anthropic`**, nie LiteLLM.

- Powód: koszt i tak musimy liczyć z `usage` × cennik (LiteLLM `response_cost`
  cicho zwraca `None`/`0` dla świeżego modelu spoza jego bundled cennika — to
  defeat-owało cały mechanizm budżetu). Skoro własny cennik jest konieczny,
  SDK `anthropic` daje resztę taniej: typowane błędy, natywny `cache_control`,
  natywne structured outputs (`messages.parse` / `output_config.format`),
  brak ciężkich zależności (LiteLLM ciągnie openai/tiktoken/aiohttp…).
- **Dodać `anthropic` do `pyproject.toml`** (+ `uv lock`).
- SDK czyta `ANTHROPIC_API_KEY` z env.

## Architektura — nowa apka `src/ai_search/`

Osobna apka w `INSTALLED_APPS`, własne migracje — izolacja od przeciążonego
`bpp`, czyste granice, testowalność w oderwaniu.

```
src/ai_search/
  __init__.py apps.py
  models.py          # AISearchQuery (log + koszt), FxRate (trwały fallback kursu)
  schema_export.py   # cache opisu schematu dla LLM (Redis + regen)
  translator.py      # SDK anthropic (NL→DSL) + walidacja + bounded retry
  pricing.py         # cennik modeli (Decimal) + liczenie cost_usd z usage
  fx.py              # kurs USD→PLN z NBP (cache + trwały fallback)
  budget.py          # guard budżetowy (dzienny/miesięczny PLN)
  prompts.py         # reguły twarde + few-shot PL→DSL (Rekord + Autor)
  views.py urls.py   # ZapytanieAIView; URL bpp:zapytanie-ai
  templates/ai_search/…
  migrations/ tests/
```

### 1. Opis schematu dla LLM (`schema_export.py`)

`djangoql-iplweb` **0.28.0** ma to gotowe:
`djangoql.llm.describe_schema_for_llm(schema)` + polecenie
`djangoql_describe_schema_for_llm`. Zwraca JSON:
`{start_model, grammar{…,negation}, models{pole:{type,nullable,operators,
relates_to/note,example,suggested_values≤20}}, examples}`.

Wołamy `describe_schema_for_llm(BppQLSchema(Rekord))` i `(Autor)`
(`BppQLSchema` z `src/bpp/djangoql_schema.py:232`; instancjonowana modelem —
`.models` to lazy BFS, jak w `ZapytanieIntrospectView`).

- **Bump `djangoql-iplweb>=0.28.0`** (obecnie zainstalowane 0.27.2, pin
  `>=0.27.2` — 0.27.2 nie ma `management/` ani `llm.py`). `uv lock`.
- **⚠ Zmierzyć rozmiar JSON-a PRZED implementacją** (KRYTYCZNE z review):
  BFS Rekordu ciągnie każdą powiązaną tabelę + `__rel` picker per FK
  (`RelPickerSchemaMixin`) + do 20 `suggested_values`, a labelki pickerów
  używają `opis_bibliograficzny_cache` (~200-znakowe cytaty). Realnie może to
  być dziesiątki tysięcy tokenów → $0,05–0,20 input/wywołanie × (1+retry).
  ```
  uv run python src/manage.py djangoql_describe_schema_for_llm bpp.Rekord \
      --schema bpp.djangoql_schema.BppQLSchema | (policz tokeny)
  ```
  Jeśli > ~30k tokenów → **strategia przycinania**: usunąć `suggested_values`
  dla pickerów, ograniczyć głębokość BFS, albo wykluczyć pola z ciężkimi
  labelkami. Do rozstrzygnięcia po pomiarze, w planie.
- **⚠ Dane do Anthropic:** `suggested_values` wysyłają **realne dane z bazy**
  (nazwiska autorów, nazwy jednostek, tytuły źródeł). Dla środowiska
  multi-hosted to decyzja o przetwarzaniu danych — udokumentować; rozważyć
  wyłączanie `suggested_values` dla wrażliwych pickerów.
- `_field_options` w `llm.py` połyka wszystkie wyjątki (`except Exception:
  return None`) → zepsuty picker cicho znika ze schematu. **Logować** w
  `schema_export.py` przy generacji, żeby to wychwycić.
- **Cache w Redis, TTL 24h** (`BPP_AI_SCHEMA_CACHE_TTL`). Regeneracja przez
  Celery beat i/lub management command. Stabilny (byte-identyczny) blok
  schematu = warunek konieczny prompt cachingu (ale patrz §pkt 4 o TTL 5 min).

### 2. Translator (`translator.py`)

Wywołanie SDK `anthropic` (`client.messages.parse`):

- **model** = `settings.BPP_AI_MODEL` (default `claude-sonnet-5`).
- **system** (blok cache'owalny, `cache_control: {"type": "ephemeral"}`):
  schema JSON (Rekord albo Autor) + reguły twarde z `prompts.py` (stringi w
  cudzysłowach, relacje kropką, listy `x in (...)`, negacja operatorem
  `!=`/`!~`/`not in`/`not startswith`/`not endswith`, brak samodzielnego `not`)
  + 10–15 few-shot PL→DSL swoistych dla BPP (rok, `autor.nazwisko ~`,
  `jednostka`, `charakter`, `typ_kbn`, listy, negacje, relacje 2 poziomy).
  **Pytanie użytkownika idzie PO bloku cache'owalnym** (osobny, nie-cache'owany).
- **`thinking={"type": "disabled"}`** — Sonnet 5 domyślnie włącza adaptive gdy
  pole pominięte; NL→DSL nie potrzebuje myślenia; walidator+retry to siatka;
  koszt przewidywalny. (Sonnet 5 akceptuje explicit `disabled`.)
- **`output_format`** = pydantic `DSLQuery{query: str|None, error: str|None}`
  (`extra="forbid"`) — natywne structured outputs Sonnet 5, `.parsed_output`.
- **`max_tokens` twardo małe** (~500 — DjangoQL query jest krótki; cap chroni
  koszt i latencję). Bez streamingu (mały output, < 16k).
- **NIE ustawiać `temperature`/`top_p`/`top_k`** — Sonnet 5 odrzuca
  niedefaultowe wartości (400).
- **`timeout`** na kliencie (~30 s) — nie wisieć w workerze bez końca.
- Obsługa `stop_reason == "refusal"` (mało prawdopodobne dla NL→DSL, ale
  sprawdzić przed czytaniem `parsed_output`).

#### Pętla walidacja → korekta (kluczowe)

Po odpowiedzi modelu, jeśli `query` nie jest `None`:

1. **Waliduj składniowo** — zbuduj przez `apply_search(qs, query,
   schema=BppZapytanieSchema)` (ten sam wywół co „zapytaniem"). Łap komplet:
   `DjangoQLError, FieldError, ValidationError, ValueError` (`zapytanie.py:428`).
2. **Przechodzi** → redirect na `bpp:zapytanie` (patrz §6).
3. **Nie przechodzi** → **zwróć błąd do modelu z konkretem**: wygenerowane
   zapytanie `<Q>` + dokładny komunikat (`str(exc)`) + **lokalizacja**
   `{line, column}` z `_error_location` (`zapytanie.py:356`). Treść retry:
   *„Poprzednie zapytanie `<Q>` zwróciło błąd DjangoQL: `<komunikat>`
   (linia L, kolumna C). Skoryguj i zwróć poprawne zapytanie."*
4. **Pętla ograniczona** — `BPP_AI_MAX_RETRIES` (default 1, cap 2). Każdy retry
   to kolejne płatne wywołanie, **liczy się do budżetu PLN** i jest sprawdzane
   guardem przed wysłaniem. Po wyczerpaniu prób — pokaż użytkownikowi ostatni
   błąd + wygenerowany query (do ręcznej poprawki w „zapytaniem").

Jeśli `query is None` — pokaż `error` z modelu (niewyrażalne w DSL), bez akcji.

- **`_error_location` przenieść do wspólnego modułu** (np.
  `src/bpp/djangoql_helpers.py`) i importować z obu miejsc — zamiast reach-in do
  prywatnej metody `bpp.views.zapytanie` z apki `ai_search`.
- Translator zwraca: `query`, `error`, listę prób (`attempts`), zbiorczy
  `usage` (in/out/cache tokens).

### 3. Koszt z `usage` (`pricing.py`)

SDK `anthropic` NIE daje gotowego kosztu — liczymy sami (to i tak było konieczne):

- Cennik w settings (Decimal, per MTok), z obsługą intro-pricingu:
  Sonnet 5 input $3 / output $15 (intro $2 / $10 **do 2026-08-31**),
  cache read ~0,1× input, cache write ~1,25× input.
- `cost_usd = (input_tokens×in + output_tokens×out + cache_read×in×0.1
  + cache_write×in×1.25) / 1e6` (Decimal).
- **Traktować `usage` puste / zerowe przy niezerowej treści jako błąd** (log +
  Rollbar) — nie logować cicho 0,00.

### 4. Prompt caching — realistyczne oczekiwania

Z review (KRYTYCZNE #2): TTL cache Anthropic to **5 min** (ephemeral). Pojedynczy
staffer pytający sporadycznie prawie zawsze zapłaci **write** (1,25×), nie
**read** (0,1×). Redis 24h trzyma prefix byte-stabilny (konieczne, nie
wystarczające). **Retry w pętli walidacji trafią w cache** (są < 5 min) — realny
zysk. Wnioski:

- Jeden `cache_control` breakpoint na końcu bloku schema+reguły; pytanie po nim.
- **Budżet `BPP_AI_DAILY_BUDGET_PLN` wyceniać przy ~1,25× niecache'owanego
  schematu na pytanie**, nie 0,1×.
- Min. cache'owalny prefix Sonnet 5 nie jest w opublikowanej tabeli (Sonnet 4.6/
  Fable 5 = 2048, Opus 4.8 = 4096). Zakładać ≥2048 i **zweryfikować
  `usage.cache_read_input_tokens > 0`** empirycznie.

### 5. Kurs USD→PLN (`fx.py`)

- Źródło: **NBP** — `https://api.nbp.pl/api/exchangerates/rates/A/USD/?format=json`
  → `rates[0].mid` (HTTPS!).
- **Cache Redis** (`BPP_AI_FX_CACHE_TTL`, default 24h). Tabela A tylko w dni
  robocze.
- **Trwały fallback w DB** (`FxRate` — wiersz z ostatnim znanym kursem +
  timestamp), nie tylko Redis: gdy Redis pusty **i** NBP down. Terminalny
  fallback (nigdy nie było zapisu): konserwatywny stały kurs z settings
  (`BPP_AI_FX_FALLBACK`, np. 4.5) + log. **Nigdy nie blokujemy feature'a z
  powodu FX** — do wyceny wystarczy ostatni znany/konserwatywny kurs.

### 6. Log + koszt (`models.py` → `AISearchQuery`)

Pola: `user` (FK, nullable), `created` (auto, **`db_index=True`**),
`model`, `pytanie`, `wygenerowany_query`, `wybrany_model_danych`,
`input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_write_tokens`,
`cost_usd` (Decimal), `fx_rate` (Decimal), `cost_pln` (Decimal),
`success` (bool), `error` (tekst, nullable), `retried` (bool).

Źródło prawdy dla budżetów (agregacja po `created` + `cost_pln`).

### 7. Guard budżetowy (`budget.py`)

- Przed **każdym** wywołaniem (także przed każdym retry): suma `cost_pln` z
  **dziś** i z **bieżącego miesiąca** (agregacja `AISearchQuery`; opcjonalnie
  licznik Redis jako cache, DB źródłem prawdy). **Strefa czasowa**: Django
  `TIME_ZONE` (nie UTC) dla granic „dziś/miesiąc".
- Porównaj z env `BPP_AI_DAILY_BUDGET_PLN` / `BPP_AI_MONTHLY_BUDGET_PLN`.
- Po przekroczeniu — **twardy blok**: komunikat „limit na dziś/miesiąc
  osiągnięty, spróbuj później lub użyj «szukaj zapytaniem»" + link do
  `bpp:zapytanie`. Zero wywołań API.
- **Brak liczników per-user/globalnych** — jedyny mechanizm to budżety PLN.
- **Race / „miękki na ostatnim zapytaniu"** (świadomie akceptowane): koszt
  znamy po wywołaniu; N równoległych żądań może przekroczyć próg o
  (N−1)×koszt. Przy zaufanym staffie i koszcie rzędu groszy–złotych — OK.
  Twardy `max_tokens` (§2) ogranicza koszt pojedynczego wywołania.

### 8. Widok i UX (`views.py`) — redirect

- URL `bpp:zapytanie-ai`, dostęp jak `zapytanie`
  (`WprowadzanieDanychOrSuperuserMixin`).
- Formularz: radio (Rekord/Autor) + textarea na pytanie PL.
- Submit (POST): guard budżetu → translator (z pętlą walidacji) →
  - sukces: **redirect na `bpp:zapytanie?model=<m>&query=<DSL>`**; pytanie PL
    w session flash (opcjonalny baner w `zapytanie.html`: „wygenerowano z: …").
  - błąd składniowy po wyczerpaniu retry / `query=null` / blok budżetu /
    błąd API: render strony AI z komunikatem (+ wygenerowany query jeśli jest).
- **Latencja (KRYTYCZNE UX):** wywołanie 3–15 s trzyma workera WSGI. Minimum:
  JS blokujący przycisk submit + stan „tłumaczę pytanie…", `timeout` ~30 s w
  SDK, przyjazny komunikat.
- **Obsługa błędów API** (`anthropic.AuthenticationError`,
  `RateLimitError`, `APITimeoutError`, `APIConnectionError`, `APIStatusError`):
  log przez `rollbar.report_exc_info()` (zgodnie z CLAUDE.md) + generyczny
  komunikat. Osobno przypadek **„klucz jest, ale odrzucony w runtime"**
  (`AuthenticationError`) — nie tylko „brak klucza".

### 9. Menu top-bar

`src/django_bpp/templates/top_bar.html` (dropdown „szukaj", ~18–43): dodać
**„przez sztuczną inteligencję"**. Gate przez **istniejący filtr** (single
source of truth, nie kopia surowego warunku):

```django
{% load query_editor %}
{% if request.user|can_use_query_editor and BPP_AI_SEARCH_ENABLED %}
    …pozycja menu…
{% endif %}
```

(`can_use_query_editor` — `src/bpp/templatetags/query_editor.py:8`, opakowuje
`user_can_use_query_editor`.) Pozycja widoczna tylko gdy feature włączony i
klucz skonfigurowany.

### 10. Konfiguracja (multi-hosted)

Env/settings (defaulty; per-tenant przez env):

- `BPP_AI_SEARCH_ENABLED` (default `False`),
- `BPP_AI_MODEL` (default `claude-sonnet-5`),
- `ANTHROPIC_API_KEY` (czyta SDK),
- `BPP_AI_DAILY_BUDGET_PLN`, `BPP_AI_MONTHLY_BUDGET_PLN`,
- `BPP_AI_MAX_RETRIES` (default 1, cap 2),
- `BPP_AI_PRICING` (cennik Decimal per model; default z intro-datą),
- `BPP_AI_FX_FALLBACK` (konserwatywny kurs terminalny, np. 4.5),
- `BPP_AI_SCHEMA_CACHE_TTL`, `BPP_AI_FX_CACHE_TTL` (default 24h),
- `BPP_AI_LLM_TIMEOUT` (default 30 s).

Gdy wyłączone lub brak klucza: pozycja menu ukryta, widok 404/redirect, no-op.

## Testy

- `translator` (mock SDK): poprawne tłumaczenie; walidacja→retry z konkretnym
  błędem (błąd → retry → sukces); `query=null`; `refusal`; **`usage`
  zerowe/None → błąd** (KRYTYCZNE #1); brak `temperature` w wywołaniu.
- `pricing`: liczenie `cost_usd` z usage (w tym cache read/write), intro-data.
- `fx`: NBP OK; NBP down → Redis; Redis+NBP down → `FxRate` DB; brak wszystkiego
  → `BPP_AI_FX_FALLBACK`.
- `budget`: przejście; przekroczenie dzienne/miesięczne (twardy blok);
  strefa czasowa granic; guard re-check przed każdym retry.
- `schema_export`: cache hit/miss, regen, kształt JSON dla Rekord i Autor,
  log zepsutego pickera.
- `views`: gate dostępu; happy path → **redirect z poprawnym query w GET**;
  blok budżetu; błąd API → Rollbar + komunikat; brak/nieważny klucz.
- **Accuracy 30–50 par PL→DSL** — `@pytest.mark.skipif(not ANTHROPIC_API_KEY)`,
  wykluczone z CI shardów (może wołać realny model).
- Konwencje: pytest, `@pytest.mark.django_db`, `model_bakery.baker`, bez klas.

## Migracje / baseline

- Migracja dla `AISearchQuery` + `FxRate` (apka `ai_search`).
- **`make baseline-update` przy scalaniu** (nie w gałęzi równolegle). Commit obu:
  `baseline-sql/baseline.sql` + `baseline-sql/baseline.meta.json`.

## Zależności

- **Dodać `anthropic`** do `pyproject.toml` (+ `uv lock`).
- **Bump `djangoql-iplweb>=0.28.0`** (+ `uv lock`).

## Poza zakresem iteracji 1

- Pre-flight oszacowanie kosztu (twardy sufit per-zapytanie przed wywołaniem).
- Fallback na tańszy model (Haiku) po przekroczeniu budżetu.
- Publiczny/anonimowy dostęp i limity per-IP.
- Liczniki liczby zapytań per-user/globalne.
- Model lokalny (Ollama/qwen) jako alternatywa on-premise.
- Asynchroniczne wywołanie (Celery) zamiast blokowania workera — jeśli latencja
  okaże się problemem, kandydat na iterację 2.

## Otwarte punkty do potwierdzenia w planie

- Nazwa URL/namespace (`bpp:zapytanie-ai`).
- Wynik pomiaru rozmiaru JSON-a schematu → decyzja o przycinaniu.
- Dokładny kształt banera z pytaniem PL w `zapytanie.html` (albo tylko flash).
- Min. cache'owalny prefix Sonnet 5 — weryfikacja empiryczna.
