# P4 — Unifikacja parsowania błędów PBN przez `ErrorRecord`

**Status:** Stage 1 (reader-first). Writery NIE zmieniane.
**Gałąź:** `feat/pbn-p4-reader` (stack na `feat/pbn-shims` / #609).
**Zakres wybrany przez użytkownika:** pełna **unifikacja** (nie minimalny wariant).

---

## 1. Problem

Błędy wysyłki do PBN są zapisywane w bazie jako **surowe stringi** w dwóch
polach:

- `pbn_api.SentData.exception` (`TextField`, max 65535) — zapis przez
  `str(exception)` w `SentData.objects.mark_as_failed()` oraz
  `publication_sync.py` (`exception=str(e)`).
- `pbn_export_queue.PBN_Export_Queue.komunikat` (`TextField`) — zapis przez
  `traceback.format_exc()` w `_handle_pbn_exception()`.

Odczyt (display) jest **rozproszony w 4 funkcjach**, każda z własną, kruchą
logiką parsowania tego samego stringa:

| Funkcja | Plik | Zwraca | Parser |
|---|---|---|---|
| `format_pbn_error(value, rodzaj_bledu)` | `pbn_export_queue/templatetags/pbn_queue_extras.py` | HTML (`mark_safe`) | regex na krotkę + `json.loads` |
| `parse_pbn_api_error(text)` | `pbn_export_queue/views/utils.py` | `dict` | `ast.literal_eval` + `json.loads` |
| `parse_error_details(sent_data)` | `pbn_export_queue/views/utils.py` | `dict` | `ast.literal_eval` + `json.loads` |
| `extract_pbn_error_from_komunikat(komunikat)` | `pbn_export_queue/views/utils.py` | `str \| None` | skan linii traceback |
| `exception_details(obj)` (admin) | `pbn_api/admin/sentdata.py` | `str` | hack `split('"details":')[1][:-3]` |

Każdy hack pęka przy innym kształcie danych; admin-owy `split(...)[1][:-3]`
jest szczególnie kruchy.

## 2. Formaty legacy (korpus wejściowy)

Empirycznie potwierdzone kształty stringów w bazie:

1. **Goła krotka** (z `SentData.exception`, bo `str(HttpException)` =
   `str(self.args)` = tuple-repr):
   `(400, '/api/v1/publications', '{"message":"...","details":{...}}')`
2. **Linia z prefiksem** (ostatnia linia tracebacku w `komunikat`; Python
   formatuje wyjątek jako `moduł.Klasa: str(wyjątek)`):
   `pbn_api.exceptions.HttpException: (400, '/url', '{...}')`
   lub `pbn_client.exceptions.PBNValidationError: (400, '/url', '{...}')`
   (obie ścieżki importu muszą być rozpoznawane).
3. **Pełny traceback** (`komunikat`): wieloliniowy, kończy się linią (2).
4. **Payload JSON = lista**: `(400, '/url', '[{...},{...}]')`.
5. **Payload zdegenerowany**: pusta lista `[]`, string `"..."`, liczba `42`.
6. **Prosty wyjątek bez krotki**: `pbn_api.exceptions.StatementsMissing: msg`.
7. **Nie-PBN plaintext**: `Some random error message`.
8. **Puste**: `None`, `""`.
9. **Payload z HTML/XSS** w `message`/`description`/`details` (musi być
   escapowany w HTML-owej ścieżce).

## 3. Nowy format v1 (wire format — pisany dopiero w Stage 2)

Jednoliniowy JSON, sanity-markers `v` i `kind` **oba wymagane** do rozpoznania:

```json
{"v": 1, "kind": "http", "source": "sentdata",
 "exception_class": "pbn_client.exceptions.PBNValidationError",
 "status_code": 400, "url": "/api/v1/publications",
 "content": "{...raw body...}", "message": "...", "traceback": "...",
 "truncated": false}
```

- `kind` ∈ {`http`, `generic`}.
- Limity rozmiarów (mieszczą się w 65535 pola `exception`):
  `content` 10k, `traceback` 20k (trzymany od końca), `message` 2k,
  `url` 512, cały blob ≤ 60k. Przekroczenie → `truncated=True`.
- **W Stage 1 nikt nie pisze v1.** `serialize()` istnieje i jest
  przetestowany, ale nie jest podpięty do writerów. Readery MUSZĄ już
  rozumieć v1 (reader-first) — inaczej deploy-race Stage 2 wywali stary
  proces na nowym blobie.

## 4. `ErrorRecord` + `parse()`

**Dom modułu: pakiet `pbn-client`** (`pbn_client.error_record`, wydany jako
`pbn-client` 0.2.1). To czysta, framework-niezależna wiedza o protokole PBN —
należy do pakietu, nie do monolitu. BPP importuje `from pbn_client.error_record
import parse, serialize, ErrorRecord`; w BPP zostają wyłącznie Django-owe
adaptery display (§5). Do czasu publikacji 0.2.1 na PyPI, BPP pinuje pakiet
przez `[tool.uv.sources]` (git rev) — do usunięcia po release.

### 4.1. `ErrorRecord` (frozen dataclass)

Pola wystarczające do odtworzenia outputu KAŻDEGO renderera:

| Pole | Typ | Znaczenie |
|---|---|---|
| `kind` | `str` | `"http"` \| `"generic"` |
| `source` | `str \| None` | `"sentdata"` \| `"queue"` \| `None` |
| `exception_class` | `str \| None` | pełna nazwa (`pbn_api.exceptions.HttpException`) |
| `exception_type` | `str \| None` | krótka nazwa (`HttpException`) — ostatni segment |
| `status_code` | `int \| None` | kod HTTP |
| `url` | `str \| None` | endpoint |
| `content` | `str \| None` | surowy body odpowiedzi (string JSON lub inny) |
| `content_json` | `dict \| list \| str \| int \| None` | sparsowany `content` (None gdy niepoprawny JSON) |
| `message` | `str \| None` | komunikat wyjątku / opis |
| `traceback` | `str \| None` | pełny traceback (gdy był) |
| `raw` | `str` | oryginalny wejściowy string (fallback) |
| `is_pbn_api_error` | `bool` | czy rozpoznano strukturę PBN (krotka lub prefiks PBN) |
| `wire` | `str` | proweniencja: `"v1"` \| `"legacy"` \| `"empty"` |
| `content_json_valid` | `bool` | czy `content` był poprawnym JSON-em (odróżnia `null` od błędu) |
| `truncated` | `bool` | czy przycięto przy serializacji |

`wire` jest kluczowe dla reader-first: adaptery renderują blob v1 WPROST ze
strukturalnych pól (bez `exception_line`/krotki), inaczej pokazałyby surowy
JSON. `content_json_valid` odróżnia poprawny JSON `null` (`content_json is
None`, `valid=True`) od niepoprawnego body (`valid=False`).

### 4.2. `parse(stored: str | None) -> ErrorRecord`

**Gwarancja: NIGDY nie rzuca.** Drabina rozpoznania (pierwszy match wygrywa):

1. `None`/blank → `ErrorRecord(kind="generic", raw="", is_pbn_api_error=False)`.
2. **v1 JSON**: `json.loads` daje `dict` z `v == 1` (int) i `kind` ∈ {http,
   generic} → zbuduj z pól. (Oba markery wymagane — chroni przed kolizją z
   legacy payloadem który przypadkiem jest dict-em.)
3. **Traceback**: wieloliniowy string zawierający `Traceback (most recent`
   → wyłuskaj ostatnią linię z `pbn_api.exceptions`/`pbn_client.exceptions`;
   zapamiętaj `traceback=stored`; parsuj tę linię dalej jak (4)/(5).
4. **Linia z prefiksem PBN**: `moduł.Klasa: <reszta>` gdzie moduł ∈
   {pbn_api.exceptions, pbn_client.exceptions} → `exception_class`,
   `exception_type`; `<reszta>` parsuj jak (5).
5. **Krotka**: `(code, 'url', 'json_str')` przez `ast.literal_eval`
   (≥3 elementy) → `status_code`, `url`, `content`; `content_json =
   json.loads(content)` (None gdy błąd). `is_pbn_api_error=True`,
   `kind="http"`.
6. **Prosty wyjątek**: prefiks PBN + brak krotki → `message = <reszta>`,
   `kind="generic"`, `is_pbn_api_error=True`.
7. **Plaintext fallback**: cokolwiek innego → `raw=stored`, `message=stored`,
   `is_pbn_api_error=False`, `kind="generic"`.

**DoS guard**: część-message dłuższa niż 512 znaków w ścieżce krotki →
zachowanie jak w obecnym `parse_pbn_api_error` (flaga + skrócony komunikat).

### 4.3. `serialize(rec: ErrorRecord) -> str`

v1 JSON, jednoliniowy, z limitami rozmiaru z §3. Round-trip:
`parse(serialize(rec))` zwraca rekord równoważny na polach v1. **Nie podpięty
do writerów w Stage 1.**

## 5. Renderery (podpięte pod `ErrorRecord`)

Każda z 4 funkcji display zostaje **przepisana jako cienki renderer nad
`parse()`**, zachowując **identyczny podpis i kontrakt outputu** (pinowane
testami charakteryzacyjnymi z §6):

- `format_pbn_error(value, rodzaj_bledu=None)` → `parse(value)` →
  `_render_html(rec, rodzaj_bledu)`. Ta sama logika MERYT/TECH (ukrywanie
  nagłówka), te same klasy CSS, **KAŻDA** dynamiczna wartość przez
  `escape()` (stored-XSS). Fallback: `<div class="pbn-error-text">…</div>`.
- `parse_pbn_api_error(text)` → `parse(text)` → `_render_dict(rec)` z tymi
  samymi kluczami (`is_pbn_api_error`, `error_code`, `error_endpoint`,
  `error_message`, `error_description`, `error_details_json`,
  `exception_type`, `raw_error`).
- `parse_error_details(sent_data)` → `parse(sent_data.exception)` →
  `error_code`/`error_endpoint`/`error_details` + fallback na
  `api_response_status`.
- `extract_pbn_error_from_komunikat(komunikat)` → `parse(komunikat)`;
  zwraca zrekonstruowaną „linię wyjątku" (`exception_class: content-repr`)
  lub `None` gdy brak — kontrakt jak dziś (używana potem jako wejście do
  `parse_pbn_api_error`, więc round-trip musi się zgadzać).
- `exception_details(obj)` (admin) → `parse(obj.exception)` → czytelny
  opis `details` z `content_json` (koniec hacka `split`). To jest
  **zamierzone ulepszenie** (brak testów pinujących stary hack; nowy output
  jest nadzbiorem informacyjnym). Udokumentowane jako świadoma zmiana.

## 6. Testy (TDD, byte-identyczność)

### 6.1. Testy charakteryzacyjne (siatka bezpieczeństwa)
Przed refaktorem: `test_error_record_golden.py` zdejmuje **aktualny** output
wszystkich funkcji na pełnym korpusie z §2 i asertuje **dokładną** równość.
Po refaktorze te same asercje muszą przejść → dowód byte-identyczności dla
legacy (poza świadomie zmienionym adminem, §5).

### 6.2. Testy jednostkowe `ErrorRecord`/`parse`/`serialize`
- `parse()` nigdy nie rzuca (fuzz: losowe/wrogie/binarne stringi — wszystkie
  dają `ErrorRecord`, żaden wyjątek).
- Rozpoznanie każdej gałęzi drabiny (§4.2) osobno.
- Brak kolizji legacy↔v1: legacy dict-payload BEZ `v==1` NIE łapie się jako
  v1; string `{"v":1,...}` w treści legacy nie myli parsera.
- `serialize()` respektuje limity; round-trip `parse(serialize(x))`.

### 6.3. Istniejące testy (muszą zostać zielone bez zmian)
`test_template_filters.py`, `test_utils.py` — obecny kontrakt. Nie ruszamy
asercji; służą jako dodatkowe piny.

## 7. Rollout (przypomnienie)

- **Stage 1 (ten PR):** moduł + readery rozumieją legacy ORAZ v1. Writery
  bez zmian. `serialize()` istnieje, nie podpięty.
- **Stage 2 (osobny PR, DOPIERO po wdrożeniu Stage 1 na całej flocie +
  restarcie web+celery):** writery → `serialize()`.
- **Stage 3 (później):** usunięcie parsowania legacy + backfill.

## 8. Poza zakresem Stage 1

- Zmiana writerów / migracja danych / backfill.
- Zmiana schematu bazy (pole `exception`/`komunikat` bez zmian).
- Zmiana szablonów poza tym, co wynika z identycznego HTML z `format_pbn_error`.

## 9. Rozliczenie recenzji adwersaryjnych (2× Fable)

Dwie niezależne recenzje Fable (poprawność/byte-identyczność + bezpieczeństwo).
Findingi i ich rozwiązania:

**Naprawione przed mergem (krytyczne):**
- **Reader-first zepsuty dla v1** (parse_pbn_api_error klasyfikował blob v1
  >512 jako „nie-PBN", format_pbn_error pokazywał surowy JSON): dodano jawną
  gałąź `wire == "v1"` w obu adapterach + guard >512 stosowany TYLKO do
  legacy. Pinowane `test_error_record_v1_reader.py`.
- **Totalność `parse()`**: `_try_json`/`_try_v1` łapią teraz też
  `RecursionError`/`MemoryError` (głęboki JSON z wrogiego body), a
  `_try_tuple` — `OverflowError` (`int(1e999)`). Pinowane w testach
  jednostkowych pakietu.
- **Konflacja „niepoprawny JSON" ↔ „JSON `null`"**: pole `content_json_valid`
  odróżnia oba; `_render_pbn_dict`/`parse_error_details` renderują `null`
  jak legacy („Nieoczekiwany typ odpowiedzi PBN API").
- **serialize() bez limitu na `exception_class`/`source`**: dodano capy →
  blob dowodliwie < 65535.

**Zaakceptowane jako świadome, drobne zmiany zachowania** (nietypowe wejścia,
neutralne-lub-lepsze, poza golden):
- prefiks + puste body `(400,'/x','')`: nowe `HttpException: HTTP 400 - `
  zamiast surowej krotki (regex legacy wymagał niepustego body).
- linia PBN bez `:` (wyjątek bez argumentów): `exception_type` = realna klasa
  (nie domyślne „HttpException"), `error_message` = pusty (downstream i tak
  ratuje się `raw_error`).
- body z escapowanym apostrofem/cudzysłowem: renderowane strukturalnie
  (legacy gubił je w zepsutym unescape).

**Czyste (bez findingów):** stored-XSS (wszystkie ścieżki `escape()`),
kolizja legacy↔v1 (markery `v==1`+`kind` szczelne), rozdział reader/writer
(`serialize()` niepodpięty), byte-identyczność realistycznego legacy.
