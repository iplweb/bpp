# Wyszukiwanie przez AI (`ai_search`)

Formularz „zapytaj po polsku" (`ai_search.views.ZapytanieAIView`) tłumaczy
pytanie w języku naturalnym (PL) na zapytanie [DjangoQL](https://github.com/ivelum/djangoql)
przy pomocy modelu Anthropic Claude, a następnie przekierowuje do
istniejącego edytora zapytań (`bpp:zapytanie`) z gotowym DSL-em. Aplikacja
loguje każde zapytanie wraz z kosztem w `ai_search.models.AISearchQuery`
(admin: read-only, `/admin/ai_search/aisearchquery/`).

## Zmienne środowiskowe

| Zmienna | Domyślna | Znaczenie |
|---|---|---|
| `BPP_AI_SEARCH_ENABLED` | `False` | Włącza feature (link w menu + widok; bez tego widok zwraca 404). |
| `ANTHROPIC_API_KEY` | — | Klucz API Anthropic (wymagany do realnych wywołań backendu `anthropic`; SDK `anthropic` czyta go bezpośrednio ze środowiska). |
| `BPP_AI_BACKEND` | `anthropic` | `anthropic` (natywny SDK, płatny, budżet PLN) albo `openai` (lokalny/self-hosted serwer OpenAI-compatible — darmowy, budżet nieaktywny). Patrz [„Modele lokalne"](#modele-lokalne) niżej. |
| `BPP_AI_BASE_URL` | `""` | Tylko dla `BPP_AI_BACKEND=openai` — adres API zgodny z OpenAI (np. `http://localhost:11434/v1` dla Ollama). |
| `BPP_AI_API_KEY` | `""` | Tylko dla `BPP_AI_BACKEND=openai` — klucz API (pusty dla serwerów bez auth, np. Ollama). |
| `BPP_AI_MODEL` | `claude-sonnet-5` | Model używany do tłumaczenia NL->DSL. Dla `anthropic` musi mieć wpis w `BPP_AI_PRICING` (cennik) w `settings/base.py`; dla `openai` to nazwa modelu na lokalnym serwerze (np. `qwen3:8b`). |
| `BPP_AI_DAILY_BUDGET_PLN` / `BPP_AI_MONTHLY_BUDGET_PLN` | `20` / `300` | Twarde limity kosztu (PLN); po przekroczeniu `ai_search.budget.check_budget()` blokuje kolejne zapytania (widok zwraca 200 z komunikatem, nic nie loguje). |
| `BPP_AI_MAX_RETRIES` | `1` | Ile razy `translator.translate` ponawia zapytanie do modelu po błędzie składni DjangoQL (z konkretnym komunikatem błędu, linia/kolumna). |
| `BPP_AI_LLM_TIMEOUT` | `30` | Timeout (s) klienta `anthropic.Anthropic`. |
| `BPP_AI_SCHEMA_CACHE_TTL` | `86400` | TTL (s) cache'a compact-schematu (`ai_search.schema_export`) wysyłanego jako część system prompta. |
| `BPP_AI_FX_CACHE_TTL` | `86400` | TTL (s) cache'a kursu USD->PLN (NBP). |
| `BPP_AI_FX_FALLBACK` | `4.5` | Kurs awaryjny, gdy NBP i cache/Redis zawiodą (patrz też `ai_search.models.FxRate` — trwały fallback ostatniego znanego kursu). |
| `BPP_AI_MAX_FK_OPTIONS` | `100` | Powyżej tego progu `describe_schema_for_llm` nie wypisuje pojedynczych wartości `suggest_options` dla pola FK/wyboru (schemat rośnie liniowo z liczbą opcji). |

## Dane wysyłane do Anthropic

Do modelu trafia (jako część system prompta, patrz `ai_search.prompts` +
`ai_search.schema_export`):

- **treść pytania użytkownika** (pole `pytanie`),
- **compact schema** modelu „rekord" lub „autor" — nazwy pól, typy, oraz
  **`suggested_values`/`suggest_options` — realne wartości z bazy**
  (np. lista źródeł, dyscyplin, jednostek) dla pól słownikowych, ograniczona
  przez `BPP_AI_MAX_FK_OPTIONS`. To są **dane z produkcyjnej bazy BPP**, nie
  dane osobowe pracowników/autorów per se, ale przy konfiguracji progu warto
  pamiętać, że treść trafia do zewnętrznego API (Anthropic).

Schemat jest cache'owany (`django.core.cache`, klucz
`ai_search:schema:<model_key>`) i odświeżany:

- automatycznie po wygaśnięciu TTL (`BPP_AI_SCHEMA_CACHE_TTL`),
- raz na dobę przez Celery beat (`ai_search.tasks.regenerate_schemas`,
  wpis `ai-search-regenerate-schemas` w `CELERYBEAT_SCHEDULE`,
  `src/django_bpp/settings/base.py`, 3:45 w nocy) — żeby nowe wartości
  słownikowe (nowe źródła, dyscypliny itd.) pojawiły się w schemacie bez
  czekania na wygaśnięcie cache.

## Jak zmierzyć rozmiar / podejrzeć treść schematu

```bash
# Wypisz aktualny (cache'owany, budowany w razie braku) schemat na stdout:
uv run python src/manage.py ai_search_schema_dump rekord
uv run python src/manage.py ai_search_schema_dump autor

# Wymuś regenerację (pomija cache) i zmierz rozmiar w znakach:
uv run python src/manage.py ai_search_schema_dump rekord --regenerate | wc -c
```

Polecenie drukuje też liczbę znaków na stderr (`# rekord: 1234 znaków`) —
przydatne przy dostrajaniu `BPP_AI_MAX_FK_OPTIONS`, żeby schemat (a więc i
koszt tokenów input) nie rósł niekontrolowanie wraz z bazą.

## Koszty

`ai_search.pricing.cost_usd_from_usage` liczy koszt (USD) na podstawie
`usage` zwróconego przez SDK (`input_tokens`, `output_tokens`,
`cache_read_tokens`, `cache_write_tokens`) i cennika `BPP_AI_PRICING` w
`settings/base.py` (per model, z opcjonalnym intro-pricingiem do daty).
Nieznany model w cenniku podnosi `KeyError` — widok łapie ten wyjątek,
zgłasza do Rollbar i loguje wpis z `cost_usd=0`/`cost_pln=0` zamiast cichego
zera bez śladu w monitoringu.

To dotyczy wyłącznie backendu `anthropic` — dla `BPP_AI_BACKEND=openai`
(model lokalny) widok w ogóle pomija pre-check budżetu i cennik/FX; koszt
jest zawsze logowany jako `0` (patrz sekcja niżej).

## Modele lokalne

### Backendy

`ai_search.backends.get_backend()` wybiera implementację wg
`settings.BPP_AI_BACKEND`:

- **`anthropic`** (domyślny) — natywny SDK `anthropic`, `messages.parse`
  z ustrukturyzowanym `output_format`, prompt caching (blok `system` z
  `cache_control: ephemeral`) i pełny cennik/budżet PLN
  (`ai_search.budget`, `ai_search.pricing`, `ai_search.fx`).
- **`openai`** — dowolny lokalny/self-hosted serwer zgodny z OpenAI Chat
  Completions API: [Ollama](https://ollama.com/),
  [llama.cpp/llama-server](https://github.com/ggml-org/llama.cpp),
  [vLLM](https://github.com/vllm-project/vllm),
  [LM Studio](https://lmstudio.ai/), [LocalAI](https://localai.io/) — ten
  sam backend obsługuje wszystkie, wystarczy inny `BPP_AI_BASE_URL`.
  Prosi model o JSON zgodny ze schematem `DSLQuery`
  (`response_format={"type": "json_schema", ...}`, `strict: True`),
  `temperature=0`. Darmowy: widok (`ai_search.views.ZapytanieAIView`)
  pomija pre-check budżetu, nie przekazuje `budget_check` do
  `translator.translate`, i loguje `cost_usd=0`/`fx_rate=0`/`cost_pln=0`
  bez wołania `pricing`/`fx` (model lokalny i tak nie ma wpisu w
  `BPP_AI_PRICING`).

Konfiguracja: `BPP_AI_BACKEND` / `BPP_AI_BASE_URL` / `BPP_AI_API_KEY` /
`BPP_AI_MODEL` (patrz tabela zmiennych środowiskowych wyżej).

### Przykład: Ollama

```bash
ollama pull qwen3:8b
ollama serve
```

```bash
# .env / środowisko:
BPP_AI_SEARCH_ENABLED=1
BPP_AI_BACKEND=openai
BPP_AI_BASE_URL=http://localhost:11434/v1
BPP_AI_MODEL=qwen3:8b
# BPP_AI_API_KEY pozostaw puste — Ollama nie wymaga auth.
```

Dla llama.cpp/llama-server, vLLM, LM Studio czy LocalAI zmienia się
wyłącznie `BPP_AI_BASE_URL` (i ewentualnie `BPP_AI_API_KEY`) — sam backend
(`openai`) zostaje ten sam.

### Szacunek kontekstu (WAŻNE przy doborze modelu)

Rozmiar system prompta wysyłanego do modelu to głównie compact-schema
(`ai_search.schema_export`, patrz `ai_search_schema_dump` wyżej) + reguły
i few-shot z `ai_search.prompts` + samo pytanie i miejsce na wyjście:

- **Model „rekord", ze słownikowymi wartościami**
  (`BPP_AI_MAX_FK_OPTIONS=100`, domyślne): **~31k tokenów**.
- **Model „rekord", bez wartości słownikowych** (`BPP_AI_MAX_FK_OPTIONS=0`):
  **~22k tokenów** — chudszy schemat, ale gorsza trafność dla pytań
  odwołujących się do konkretnych wartości (np. nazw źródeł/dyscyplin),
  bo model ich po prostu nie widzi.
- Do tego reguły + few-shot (~1-2k tokenów) oraz pytanie + miejsce na
  wyjście (~0,5k).
- Model „autor" ma zauważalnie mniejszy schemat niż „rekord".

**Zalecane okno kontekstu modelu lokalnego: ≥ 32k tokenów** — komfortowo
dla wariantu z wartościami słownikowymi (domyślny). Dla modeli z
kontekstem 8k/16k: ustaw `BPP_AI_MAX_FK_OPTIONS=0` (chudszy ~22k schemat)
i licz się z ciaśniejszym zapasem na resztę promptu; ewentualnie ogranicz
się do modeli o szerszym oknie.

### Zalecane modele OSS

Klasa: mały-średni model instruct, dobry w ustrukturyzowanym JSON,
kontekst ≥32k, rozumiejący polski (samo pytanie jest po polsku — DSL
wyjściowy jest już w tokenach angielskich/DjangoQL):

- **Qwen3** — rekomendacja główna (najlepszy stosunek JSON+PL wśród
  modeli tej klasy). **4B/8B** dla lekkich instalacji, **14B/32B** dla
  lepszej trafności na pytaniach dwuznacznych po polsku.
  **Uwaga:** Qwen3 domyślnie ma włączony tryb „thinking" — potrafi
  wygenerować blok rozumowania PRZED właściwym JSON-em, co przy stałym
  `max_tokens=500` (patrz `backends.py`) grozi ucięciem odpowiedzi zanim
  dojdzie do samego JSON-a. Wyłącz myślenie (np. prompt kończący się
  `/no_think` albo odpowiednia flaga serwera inferencji). Walidator
  DjangoQL + bounded-retry i tak wyłapią taki przypadek (zwrócony
  niepoprawny JSON), ale lepiej uniknąć strat tokenów/czasu i wyłączyć
  myślenie u źródła.
- **Llama 3.1 8B** (128k ctx), **Gemma 2 9B**, **Mistral** — alternatywy,
  jeśli Qwen3 nie jest dostępny lub preferowany.
- Dla twardej gwarancji poprawnej składni JSON: **llama.cpp z GBNF**
  (grammar-constrained decoding) — wymusza strukturę na poziomie
  dekodowania, niezależnie od jakości modelu.

**Uwaga kluczowa:** niezależnie od wybranego modelu lokalnego, gwarancją
poprawności końcowego zapytania jest walidator DjangoQL
(`translator.validate_query`, realny parser + `BppQLSchema`) w połączeniu
z bounded-retry (do `BPP_AI_MAX_RETRIES`, max. 2) — to jest mechanizm
**niezależny od backendu**. Słabszy model lokalny, który zwróci błędną
składnię, dostaje z powrotem dokładny komunikat błędu (linia/kolumna) i
ma szansę się poprawić, zupełnie tak samo jak przy backendzie
`anthropic`.
