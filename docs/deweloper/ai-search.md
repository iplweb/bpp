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
| `ANTHROPIC_API_KEY` | — | Klucz API Anthropic (wymagany do realnych wywołań; SDK `anthropic` czyta go bezpośrednio ze środowiska). |
| `BPP_AI_MODEL` | `claude-sonnet-5` | Model używany do tłumaczenia NL->DSL; musi mieć wpis w `BPP_AI_PRICING` (cennik) w `settings/base.py`. |
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
