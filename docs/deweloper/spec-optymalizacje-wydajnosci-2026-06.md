# Spec: optymalizacje wydajności (czerwiec 2026)

Analiza wydajności przeprowadzona 2026-06-10 (gałąź `dev`), jako
kontynuacja audytu indeksów
([audyt-indeksow-i-zapytan-2026-06.md](audyt-indeksow-i-zapytan-2026-06.md))
i optymalizacji triggera z migracji `0421` (#311, #309). Obejmuje trzy
warstwy: trigger/`bpp_rekord_mat`, warstwę ORM/zapytań oraz pipeline
CSS/JS. Każda pozycja ma status, szacowany wysiłek i sposób weryfikacji.

## Priorytety (ranking)

| # | Zmiana | Warstwa | Wysiłek | Wpływ |
|---|--------|---------|---------|-------|
| 1 | Trigger: bez `DELETE` przy INSERT/UPDATE (kaskada na `bpp_autorzy_mat`) | DB | mała migracja SQL | **wysoki** — każda edycja, import, flush denorm |
| 2 | `ContentType.objects.get_for_id()` w `Rekord.content_type` | ORM | one-liner | **wysoki** — eksporty/listy (2×N zapytań → 0) |
| 3 | Usunięcie `plpy.subtransaction()` z triggera | DB | one-liner | wysoki przy masowych operacjach |
| 4 | Multiseek: `count()` złączony z agregatem `sumy` (1 skan zamiast 2) | ORM | mały | średnio-wysoki na wolnych wyszukiwaniach |
| 5 | Frontend: Tone.js lazy-load poza `bundle.js` | JS | mały | średni — pierwsze wejście każdego usera |
| 6 | `COMPRESS_JS_FILTERS = []` (wejścia już zminifikowane) | JS | trywialny | mało-średni (czas startu kontenera) |
| 7 | Browse: zbędne `count()`/`exists()` (LataView/RokView), `.only()`+`.distinct()` w API | ORM | mały | mało-średni |
| 8 | Selektywne `@include foundation-*` (~−150 KB CSS/motyw) | CSS | średni | średni — first paint stron publicznych |
| 9 | Test + fix edge'a `UPDATE ... autor_id` w triggerze (poprawność!) | DB | mały | poprawność, nie perf |
| 10 | Długoterminowo: triggery statement-level z transition tables; benchmark GIN vs GiST dla `search_index` | DB | duży | tylko jeśli 1–3 nie wystarczą |

---

## Warstwa 1: trigger `bpp_refresh_cache()` / `bpp_rekord_mat`

Stan obecny: `src/bpp/migrations/0421_cache_trigger_pk_filter.sql:449-573`
— PL/Python `FOR EACH ROW` na 8 tabelach, routing do widoków per-typ,
filtr po surowym PK (`object_id_raw`, Index Cond), deterministyczny
advisory lock, upsert `ON CONFLICT (id) DO UPDATE`. Architektura po
0421 jest zdrowa; poniższe punkty to pozostałe rezerwy.

### 1.1. DELETE-before-upsert kaskaduje na `bpp_autorzy_mat` (PRIORYTET 1)

**Problem.** `upsert()` (linia 527) zawsze wykonuje
`DELETE FROM bpp_rekord_mat WHERE id = ...` przed
`INSERT ... ON CONFLICT`. Komentarz przy linii 560 wprost przyznaje:
DELETE kaskaduje (FK) na `bpp_autorzy_mat`. Edycja tytułu publikacji
z 50 autorami = 1 DELETE + 1 INSERT w `bpp_rekord_mat` (~17 indeksów
do odświeżenia) **plus** 50 kaskadowych DELETE + 50 re-INSERT w
`bpp_autorzy_mat` (~5 indeksów każdy).

Dodatkowy mnożnik: denorm (`opis_bibliograficzny_cache` z
`@depend_on_related("..._Autor", ...)`) przy każdej edycji autora
robi w końcu UPDATE wiersza publikacji → pełny cykl kaskady. Jedna
edycja autora ≈ dwa pełne odświeżenia rekordu.

**Dlaczego DELETE jest zbędny przy INSERT/UPDATE.** Widoki per-typ to
czyste `SELECT ... FROM tabela_bazowa GROUP BY id` — wiersz tabeli
bazowej nie może „wypaść" z własnego widoku. `ON CONFLICT DO UPDATE`
w pełni obsługuje przypadek istniejącego wiersza. DELETE jest potrzebny
**wyłącznie** dla `event == "DELETE"`.

**Fix.** W `upsert()`:

```python
if event == "DELETE":
    plpy.execute("DELETE FROM " + mat_table + " WHERE " + mat_where)
    return
# INSERT ... ON CONFLICT (id) DO UPDATE ... (bez wstępnego DELETE)
```

Uwaga: dla ścieżki `bpp_autorzy_mat` z `autor_extra` DELETE przy
UPDATE też do usunięcia, ALE patrz pkt 1.4 (zmiana `autor_id` in-place)
— oba punkty wdrożyć razem.

**Korzyści.** Brak wipe/re-insert całego `bpp_autorzy_mat` per edycja
publikacji; odświeżenia stają się zwykłymi UPDATE (HOT-friendly — gdy
kolumny indeksowane się nie zmieniły, indeksy wtórne nietknięte);
mniej dead tuples / pracy autovacuum; tańsze masowe importy
i `denorm.rebuildall()`.

**Opcjonalne wzmocnienie.** `DO UPDATE SET ... WHERE
bpp_rekord_mat IS DISTINCT FROM EXCLUDED` — pomija zapis, gdy nic się
nie zmieniło (denorm flush często re-zapisuje niezmienione wiersze).

**Weryfikacja.** Benchmark na zrzucie produkcyjnym
(`run-site --from-dump`): czas
`UPDATE bpp_wydawnictwo_ciagle SET ostatnio_zmieniony = NOW()` na
kilku tysiącach wierszy przed/po + `pg_stat_user_tables.n_dead_tup`
dla obu tabel mat. Testy: istniejące testy triggera + nowy test
„edycja publikacji nie zmienia zawartości bpp_autorzy_mat".

**Status: ✅ zrobione** (PR #352, migracja `0429_cache_trigger_v3`;
benchmark syntetyczny: bulk UPDATE 100 pub × 10 aut. 1.7× szybciej,
50 pub × 30 aut. 2.8× szybciej).

### 1.2. `plpy.subtransaction()` per wiersz (PRIORYTET 3)

**Problem.** Linia 558 — każde odpalenie triggera otwiera
subtransakcję (zużywa XID). Po przekroczeniu **64 subxactów** w jednej
transakcji backend spilluje do SLRU `pg_subtrans` i sprawdzanie
widoczności gwałtownie zwalnia (znany klif wydajnościowy). Masowy
import / `rebuildall` w jednej transakcji trafia dokładnie w to.
W kodzie nie ma `try/except` wokół subtransakcji — niczego nie łapie,
więc nie pełni funkcji recovery.

**Fix.** Usunąć `with plpy.subtransaction():` (zostawić ciało).
Jeśli była intencja izolacji błędów — udokumentować jaką i pokryć
testem; w obecnej formie wyjątek i tak propaguje i wywala transakcję.

**Weryfikacja.** Benchmark jak w 1.1 (szczególnie pojedyncza
transakcja z >64 zmienionymi wierszami).

**Status: ✅ zrobione** (PR #352, migracja `0429_cache_trigger_v3`).

### 1.3. `liczba_autorow` — eventual consistency przez denorm (DOKUMENTACJA)

Edycje through-table ustawiają `refresh_rekord = False`, więc
`liczba_autorow` w `bpp_rekord_mat` aktualizuje się dopiero, gdy flush
denorm dotknie wiersza publikacji. Zamierzone, ale nieudokumentowane —
przy opóźnionej kolejce denorm listy pokazują przestarzałą liczbę
autorów. Akcja: komentarz w SQL + nota w mapa-kodu.md.

### 1.4. Bug poprawności: `UPDATE` z `TD["old"]` (PRIORYTET 9)

**Problem.** Dla `UPDATE` trigger czyta tylko `TD["old"]` (linia 467).
Jeśli na wierszu `*_autor` ktoś zmieni `autor_id` (lub `rekord_id`)
in-place: DELETE usuwa wiersz mat starego autora, a
`INSERT ... WHERE autor_id = <stary>` nie znajduje nic → wiersz
**nowego** autora nie trafia do `bpp_autorzy_mat` aż do następnego
dotknięcia rekordu.

**Fix.** Przy `UPDATE` porównać tożsamości old/new
(`rekord_id`, `autor_id`); gdy różne — odświeżyć obie. Najpierw test
reprodukujący (UPDATE `autor_id` przez ORM/SQL + asercja na zawartość
`bpp_autorzy_mat`).

**Status: ✅ zrobione** (PR #352) — bug potwierdzony czerwonym testem;
v3 czyta `TD["new"]`, a upsert po stabilnym `id = ARRAY[ct,
pk-wiersza-through]` aktualizuje wiersz w miejscu. Przy okazji wykryty
i naprawiony DRUGI bug v2: DELETE jednej z dwóch ról autora
(aut. + red.) kasował z `bpp_autorzy_mat` oba wiersze (DELETE po
`(rekord_id, autor_id)` zamiast po id wiersza mat).

### 1.5. Indeksy na tabelach mat — follow-up po 1.1

- Po wdrożeniu 1.1 wzorzec zapisu się zmienia → powtórzyć audyt
  `pg_stat_user_indexes.idx_scan` na żywej bazie (jak PR #315/#317);
  ~17 indeksów na czystej tabeli-cache to nadal spory narzut upsertów.
- `bpp_rekord_mat_search_index_idx` jest **GiST**
  (`0001_cache_init.sql`). Dla tsvector **GIN** czyta istotnie szybciej
  (GiST jest stratny — recheck na heapie); pisze wolniej, ale z
  `fastupdate = on` i mniejszym churn-em po 1.1 warto zbenchmarkować
  na zrzucie produkcyjnym, jeśli latencja wyszukiwania pełnotekstowego
  ma znaczenie.

### 1.6. Długoterminowo: triggery statement-level (PRIORYTET 10)

Masowe UPDATE odpalają całą procedurę per wiersz (lock, SELECT z GROUP
BY, upsert). PostgreSQL 10+ wspiera `AFTER ... FOR EACH STATEMENT` z
transition tables (`REFERENCING NEW TABLE AS new_rows`) — jeden fire
odświeża wszystkie PK jednym
`INSERT ... SELECT ... WHERE object_id_raw IN (SELECT ...) ON CONFLICT`.
Większy refactor — podejmować tylko, jeśli ścieżki bulk pozostaną
wolne po 1.1/1.2.

---

## Warstwa 2: ORM / zapytania

### 2.1. `Rekord.content_type` omija cache ContentType (PRIORYTET 2)

**Problem.** `src/bpp/models/cache/rekord.py:277-283`:

```python
@cached_property
def content_type(self):
    return ContentType.objects.get(pk=self.id[0])   # realne zapytanie!
```

`ContentTypeManager` cache'uje `get_for_id()` / `get_for_model()`
procesowo, ale **goły `.get(pk=...)` nie jest cache'owany** —
`@cached_property` pomaga tylko w obrębie jednej instancji. Eksport
multiseek (`src/bpp/views/mymultiseek.py:255-282`,
`_admin_change_url` + `describe_content_type`) = **2 dodatkowe
zapytania na każdy eksportowany wiersz** (do
`MULTISEEK_EXPORT_MAX_ROWS`). Ten sam koszt wszędzie, gdzie listy
`Rekord` dotykają `original` / `content_type` / linków do admina.

**Fix.** `ContentType.objects.get_for_id(self.id[0])` w
`content_type` i `describe_content_type`.

**Niuans (cacheops).** W produkcji `contenttypes.contenttype` jest
cache'owany przez cacheops (`production.py`, `CACHEOPS`), więc
`.get(pk=...)` to tam round-trip do Redisa per wiersz, nie SQL.
Fix nadal słuszny: `get_for_id` to procesowy dict — zero sieci.
W testach cacheops jest wyłączony (`test.py`), więc liczenie zapytań
jest deterministyczne.

**Weryfikacja.** Test z `django_assert_num_queries` na
`_iter_export_rows` dla ≥2 rekordów różnych typów.

**Status: ✅ zrobione** (branch `perf/orm-quick-wins`,
`test_cache/test_content_type_cache.py`).

### 2.2. Multiseek: dwa pełne skany zamiast jednego (PRIORYTET 4)

**Problem.** `src/bpp/views/mymultiseek.py:162-182` —
`qset.count()` (linia 170; DISTINCT + join do `bpp_autorzy_mat` to
z natury najdroższa część) oraz, dla raportów punktowanych,
`qset.aggregate(Sum × 5)` (linia 176) — **drugi pełny skan tego
samego wyniku**.

**Fix.** Złączyć: `qset.aggregate(Count("pk"), Sum(...), ...)` —
jeden skan; `paginator_count` z tego samego słownika.

**Do sprawdzenia przy okazji (poprawność).** `Sum` po queryset-cie
z `.distinct()` i joinem autorów — nowsze Django opakowuje distinct
w subquery przy agregacji, ale warto mieć test, że sumy nie są
zawyżone przez duplikację z joina.

**Status: ✅ zrobione** (branch `perf/orm-quick-wins`,
`test_views/test_mymultiseek_query_count.py`).

### 2.3. Browse: zbędne zapytania (PRIORYTET 7)

`src/bpp/views/browse.py` (zweryfikowane):

- **`LataView.get_context_data`** (~linia 500):
  `Rekord.objects.count()` — pełny count tabeli mat przy każdym
  renderze, a `total_publications` to po prostu
  `sum(y["count"] for y in context["years"])` z GROUP BY, który już
  wykonano.
- **`RokView`** (~547-556): dwa `.exists()` (prev/next rok) +
  `filter(rok=year).count()` — przy czym `ListView` z
  `paginate_by=50` już wykonał ten sam COUNT dla paginatora
  (`context["paginator"].count`). Prev/next jednym zapytaniem:
  `Rekord.objects.filter(rok__in=[y-1, y+1]).values_list("rok", flat=True).distinct()`.

**Status: ✅ zrobione** (branch `perf/orm-quick-wins`,
`test_views/test_browse/test_browse_query_count.py`).

### 2.4. `RecentAuthorPublicationsAPI` (PRIORYTET 7)

`src/api_v1/viewsets/recent_author_publications.py:31-55`. To **nie**
jest N+1 (wszystkie pola w pętli to kolumny tabeli mat, jedno
zapytanie), ale:

- pobiera wszystkie ~47 kolumn, w tym tsvector `search_index`, dla
  25 wierszy → dodać
  `.only("id", "slug", "opis_bibliograficzny_cache", "ostatnio_zmieniony")`;
- join `autorzy__autor` bez `.distinct()` → autor występujący na
  rekordzie dwukrotnie (np. autor + redaktor) daje duplikaty i mniej
  niż 25 unikalnych publikacji.

**Status: ✅ zrobione** (branch `perf/orm-quick-wins`,
`api_v1/tests/test_autor_recent_publications.py`).

### 2.5. Drobiazgi per-strona (niski priorytet)

- `Rekord.ma_punktacje_sloty` (`rekord.py:302-310`) — dwa `.exists()`;
  da się jednym (`Exists`/union). Tylko strona szczegółów.
- Strona autora (`autor.html` + `Autor.prace_w_latach`,
  `autor.py:366`) — kilka osobnych zapytań DISTINCT per render;
  łączyć tylko, jeśli pojawi się w slow logach.

---

## Warstwa 3: pipeline CSS/JS (Grunt + dart-sass + esbuild)

Stan obecny jest dobry: dart-sass (modern-compiler), esbuild,
motywy budowane współbieżnie, lazy bundle dla ciężkich stron grafów
(`cytoscape-bundle.js` 837 KB, `three-bundle.js` tylko strona 3D),
plotly tylko na stronach metryk, hash przez `CACHE-<VERSION>/` +
`TolerantManifestStaticFilesStorage`. Pozostałe rezerwy:

### 3.1. Tone.js w głównym bundle (PRIORYTET 5)

**Problem.** `bundle.js` = **1,54 MB** po minifikacji, ładowany na
każdej stronie (`bare.html:66`). Tone.js
(`src/bpp/static/bpp/js/bundle-entry.js:43-44`,
`window.Tone = Tone`) służy wyłącznie dźwiękom powiadomień dla
zalogowanych — a jest jednym z największych składników bundle'a.

**Fix.** Wydzielić do lazy chunka: `await import("tone")` przy
pierwszym powiadomieniu, albo osobny `<script defer>` tylko dla
zalogowanych. Sprawdzić konsumentów `window.Tone` (linia 74 trzyma
referencję) i kod powiadomień w `notifications`.

**Weryfikacja.** Rozmiar `bundle.js` przed/po; smoke-test dźwięku
powiadomienia (test Playwright lub ręcznie przez `run-site`).

**Status: ✅ zrobione** (branch `perf/frontend-bundle`) — okazało się
LEPIEJ niż w spec: Tone.js to był martwy kod. Jedyny konsument
(`notifications-chime.js` z channels_broadcast) nie jest w ogóle
ładowany, `enableChime()` nigdzie nie jest wołane, a komunikaty idą
z `sound: false`. Usunięty import + zależność `tone` z package.json.
Bundle: 1 541 543 B → 943 122 B (**−598 KB, −39%**). Smoke-test
przeglądarkowy (run-site + Playwright): strony działają,
channelsBroadcast/Mustache/htmx/jQuery/Foundation obecne, zero błędów
konsoli związanych z bundle.

### 3.2. `COMPRESS_JS_FILTERS = []` (PRIORYTET 6)

**Problem.** `src/django_bpp/settings/base.py:585` —
`rJSMinFilter` re-minifikuje już-zminifikowany przez esbuild 1,5 MB
`bundle.js` podczas `manage.py compress` na starcie kontenera. Zysk
~0 bajtów, koszt czasu startu + ryzyko: regexowe minifikatory
potrafią zepsuć nowoczesną składnię, którą emituje AST-owy esbuild
(edge case'y ASI).

**Fix.** `COMPRESS_JS_FILTERS = []`. **Nie** usuwać samego
`{% compress js %}` — komentarz w `bare.html:61-64` wyjaśnia, że
compressor celowo produkuje hashowany artefakt ze stabilnej nazwy
`bundle.js`. Analogicznie rozważyć zdjęcie `CSSMinFilter` z
`COMPRESS_CSS_FILTERS` (dart-sass już emituje `style: compressed`) —
ale uwaga: przez `{% compress css %}` przechodzą też nie-zminifikowane
pliki spoza SCSS pipeline'u (jqueryui, select2 itd., `bare.html:45-58`)
— sprawdzić każdy przed zdjęciem filtra CSS.

**Weryfikacja.** Czas `manage.py compress --force` przed/po; diff
rozmiarów plików w `CACHE-*/`.

**Status: ✅ zrobione** (branch `perf/frontend-bundle`) —
`COMPRESS_JS_FILTERS = []`, filtry CSS zostają (CssAbsoluteFilter
przepisuje względne `url()` przy konkatenacji — load-bearing;
CSSMinFilter potrzebny dla nie-zminifikowanych wejść spoza SCSS).

### 3.3. Selektywna kompilacja Foundation (PRIORYTET 8)

**Problem.** Każdy `app-*.scss` robi pełny zestaw ~41
`@include foundation-*` → ~300 KB CSS na motyw (zweryfikowane:
`app-*.css` 304–307 KB). Serwowany jest jeden motyw, ale 300 KB
render-blocking CSS to główna dźwignia first paint stron publicznych.

**Fix.** Audyt użycia komponentów w templates (kandydaci do
wycięcia: orbit, drilldown, slider, switch, responsive-embed…),
wspólny `_foundation-selective.scss` z faktycznie używanymi
include'ami, import w 6 motywach. Po zmianie `grunt build`
(zgodnie z [budowanie-css.md](budowanie-css.md)). Typowy zysk: ~50%.

**Weryfikacja.** Rozmiar `app-*.css` przed/po; wizualna regresja
kluczowych stron (multiseek, strona autora, rekord) przez `run-site`.

**Status: ✅ zrobione** (branch `perf/foundation-diet`) — z ważną
korektą szacunku: audyt wykazał tylko **9** komponentów bez użycia
(accordion-menu, drilldown-menu, responsive-embed, media-object,
off-canvas, orbit, slider, switch, thumbnail); ciężkie komponenty
(gridy, forms, typography, button) są używane. Realny zysk:
**−16,5 KB/motyw (−5,4%)**, nie ~150 KB. Lista include'ów wydzielona
do wspólnego `_foundation-includes.scss` (1 plik zamiast 6 kopii).
Weryfikacja wizualna (run-site + Playwright, screenshoty): top-bar,
breadcrumbs, callout, formularz multiseek — bez regresji.

**Follow-up (zmierzony, świadomie odłożony):** `foundation-grid`
(float) i `foundation-flex-grid` emitują nakładające się reguły
`.row/.columns`; usunięcie float-grida dałoby kolejne **−17,7 KB**
(289,7 → 272,0 KB), ale zmienia kaskadę (clearfixy) i wymaga
pełnej regresji wizualnej — osobny PR, jeśli warto.

### 3.4. Nie robić (świadomie odrzucone)

- **Wymiana Grunta na webpack/Vite** — pipeline jest już szybki
  (dart-sass + esbuild); przepisywanie = ryzyko bez zysku.
- **Usuwanie `{% compress %}`** — patrz 3.2; pełni rolę
  cache-bustingu dla `bundle.js`.
- **Wycinanie plotly z `package.json`** — nie trafia do bundle'a ani
  do staticroot poza stronami metryk; 98 MB w `node_modules` boli
  tylko build stage obrazu, który i tak jest multi-stage.

---

## Plan wdrożenia (proponowane PR-y)

1. **PR „quick wins ORM"** — pkt 2.1 (`get_for_id`), 2.2 (jeden
   agregat), 2.3, 2.4. Testy `django_assert_num_queries` + istniejąca
   suita. Mały, bezpieczny, mierzalny.
2. **PR „trigger v3"** — pkt 1.1 + 1.2 + 1.4 razem (jedna migracja SQL
   `CREATE OR REPLACE FUNCTION`, wzór: 0421). Przed merge: benchmark
   na zrzucie produkcyjnym (`run-site --from-dump`), test braku
   kaskady, test edge'a `autor_id`.
3. **PR „frontend"** — pkt 3.1 + 3.2 (lazy Tone.js, filtry
   compressora). Niezależny od 1 i 2.
4. **PR „Foundation diet"** — pkt 3.3, osobno (dotyka 6 motywów,
   wymaga przeglądu wizualnego).
5. **Follow-up** — pkt 1.5 (re-audyt indeksów po zmianie wzorca
   zapisu), ewentualnie 1.6/GIN po pomiarach.

## Metodologia pomiaru (wspólna dla PR 1–2)

- Zrzut produkcyjny przez `uv run run-site run --from-dump PATH`.
- Zapytania: `django_assert_num_queries` w testach; ręcznie
  `EXPLAIN (ANALYZE, BUFFERS)` przez psql na porcie z
  `.dev_helpers_pg_port`.
- Trigger: czas masowego UPDATE (1k/10k wierszy) + `n_dead_tup`
  z `pg_stat_user_tables` przed/po; dla 1.2 — jedna transakcja
  z >64 zmienionymi wierszami.
- Frontend: rozmiary plików w `src/bpp/static/bpp/js/dist/` i
  `CACHE-*/`; czas `manage.py compress --force`.
