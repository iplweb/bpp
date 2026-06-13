# Spec: `bpp_refresh_cache` — port PL/Python → PL/pgSQL + bramka UPDATE (czerwiec 2026)

Dotyczy funkcji triggera `bpp_refresh_cache` materializującej `bpp_rekord_mat` /
`bpp_autorzy_mat`. Follow-up do
[spec-optymalizacje-wydajnosci-2026-06.md](spec-optymalizacje-wydajnosci-2026-06.md)
(trigger v3 / migracje 0421+0429). Cel: **narzut per fire** (port języka) i
**jałowy churn** odświeżeń (bramka). Likwidacja `plpython3u` z obrazu (ten port
jest jej częścią) ma osobny spec:
[spec-pozegnanie-z-plpython-2026-06.md](spec-pozegnanie-z-plpython-2026-06.md).

Liczby z benchmarku na realnym zrzucie produkcyjnym (`db-backup-20260603`,
122 232 rekordy), schemat v3 (0421+0429), tabela `bpp_wydawnictwo_ciagle`, ścieżka
UPDATE, PostgreSQL 18.

## Priorytety

| # | Zmiana | Wysiłek | Wpływ |
|---|--------|---------|-------|
| 1 | Port `bpp_refresh_cache` PL/Python → **PL/pgSQL** (statyczny upsert generowany z katalogu) | średni | **~2,2–2,3× na KAŻDYM odpaleniu** (import, flush denorm, edycja, rebuildall) |
| 2 | **Bramka `WHEN`** (lista kolumn z `pg_depend`) na UPDATE; INSERT/DELETE bezwarunkowe | średni | pomija jałowe odświeżenia na ścieżkach wsadowych nie-bumpujących `auto_now` |

---

## 1. Dowód: benchmark wariantów

**Metodologia.** Bulk `UPDATE` 2000 wierszy, `min` z 5 prób (1 warm-up odrzucona),
każda w `BEGIN … ROLLBACK` (`VACUUM ANALYZE` przed każdą komórką). Czas serwerowo
(`clock_timestamp()` w `bench_update`). `mat_wr` = zapisy do `bpp_rekord_mat` w
transakcji (`pg_stat_xact_user_tables`): **0 = refresh pominięty**, 2000 = odpalił.
V0 = combined cache-trigger; triggery denorm `d_aft` aktywne we wszystkich
wariantach (stały narzut, nie zaburza porównania względnego).

**Klasy zapisu.** WC1 = zmiana taniej kolumny cached (`punkty_kbn+1`); WC2 = no-op
na kolumnie TOAST (`opis_bibliograficzny_cache = opis_…`, jak jałowy re-zapis
denormu); WC3 = zmiana kolumny **spoza widoku** (`weryfikacja_punktacji`, jak
wsadowy bookkeeping).

| Wariant | WC1 cached | WC2 no-op TOAST | WC3 non-cached |
|---|---|---|---|
| **V0** PL/Python, bez bramki *(= baseline dev v3)* | 1333 ms · fire | 995 ms · fire | 1132 ms · fire |
| **VA** PL/Python + bramka **całowierszowa** | 1206 ms · fire | **277 ms · skip** | 1029 ms · fire |
| **VB** PL/Python + bramka **lista-kolumn** | 1056 ms · fire | **240 ms · skip** | **269 ms · skip** |
| **VC** **PL/pgSQL** statyczny, bez bramki | **570 ms** · fire | 448 ms · fire | 482 ms · fire |
| **VD** **PL/pgSQL + bramka lista-kolumn** *(config docelowy)* | 604 ms · fire | **222 ms · skip** | **~250 ms · skip** |

(per wiersz: V0 ≈ 0,50–0,67 ms; VC/VD-fire ≈ 0,29–0,30 ms; skip ≈ 0,11–0,14 ms)

Kolumna WC1 jest w obrębie szumu Docker-on-Mac (~10–20%), więc mnożnik portu
liczymy z **czystych** komórek WC2/WC3 (VC vs V0 — oba bez bramki, oba fire, różni
tylko język): WC2 995/448 = **2,22×**, WC3 1132/482 = **2,35×**.

Port jest **semantycznie neutralny**: agregat `md5` po wszystkich 65 728 wierszach
ciagle, `bpp_rekord_mat` po V0 vs po VC — **identyczny**.

### Wnioski

1. **Wyjście z PL/Python to największa dźwignia: ~2,2–2,3× na każdym fire.** Narzut
   wrappera PL/Python (0,2–0,4 ms/wiersz: marshaling `TD["old"]`/`TD["new"]` =
   2×~78 kolumn datum→PyObject; **brak cache planu** w `plpy.execute(string)`;
   interpreter) jest rzędu samej pracy refreshu (~0,29 ms w VC). Na widoku pre-0421
   (71 ms/wiersz) niewidoczne; na v3 dominuje.
2. **Koszt porównania bramki ≈ 0,11–0,14 ms/wiersz** (~¼ refreshu v3), ale skip
   oszczędza cały refresh. Inkrementalna wartość bramki maleje po porcie (~0,38
   ms/wiersz względem plpython V0, ale ~0,11 względem plpgsql-fire). Stąd: **port
   najpierw, bramka po pomiarze**.
3. **Skip na klasie non-cached działa tylko przy bramce lista-kolumn** (VB/VD; VA
   nie pomija WC3) i tylko dla zapisów nie-bumpujących `auto_now` (patrz §3).

**Synteza:** dźwignie ortogonalne → **VD** wygrywa w każdej klasie.

---

## 2. Zmiana 1 — port `bpp_refresh_cache` na PL/pgSQL

**Co.** Statyczne funkcje PL/pgSQL per tabela zamiast jednej dynamicznej PL/Python:
`INSERT INTO bpp_rekord_mat (<kolumny>) SELECT <kolumny> FROM <widok> WHERE
object_id_raw = NEW.id ON CONFLICT (id) DO UPDATE SET …`.

**Dlaczego się da.** **Widok jest kontraktem kolumn** — `bpp_*_view` jawnie wylicza
wszystkie kolumny `mat` (+ `object_id_raw`). Listy generujemy **raz, w czasie
migracji** (gdzie koszt introspekcji nie ma znaczenia) i wklejamy na sztywno.
Runtime dostaje statyczny SQL z **cache'owanym planem**, zero introspekcji.

**Generator-migracja** (Załącznik A): `RunPython` czyta kolumny `bpp_rekord_mat`,
składa `INSERT/SELECT/SET`, robi `CREATE OR REPLACE FUNCTION`. Gdy widok się zmienia
→ re-run generatora. Introspekcja: hot-path → migrate-path.

**Zakres.** 5 typów (`ciagle`, `zwarte`, `patent`, `praca_doktorska`,
`praca_habilitacyjna`) + 3 through-table. Semantyka v3 do zachowania **dokładnie**
(pełna suita testów + kanarek z §3):
- through-table → odświeża **tylko jeden wiersz autora** (`object_id_raw` +
  `autor_id`), nie cały rekord;
- doktorat/habilitacja → `DELETE + INSERT` na `bpp_autorzy_mat` (widok `*_autorzy`
  ma INNER JOIN do `bpp_autor`);
- DELETE po `id = ARRAY[ct, pk-wiersza]`, nie po `(rekord_id, autor_id)`;
- UPDATE czyta `NEW`; advisory lock `(content_type_id, object_id)`.

**Pułapki portu (KRYTYCZNE)** — PoC pokrył tylko rekord/UPDATE dla `ciagle`:

1. **Mapowanie POZYCYJNE, nie po nazwie, dla widoków `*_autorzy`.**
   `bpp_praca_doktorska_autorzy` nazywa kolumnę-tablicę `"array"`, a
   `bpp_praca_habilitacyjna_autorzy` — `id` (niespójnie). `SELECT <po nazwie>` jest
   OK dla widoków *rekord* (nazwy = kolumny `mat`), ale dla `*_autorzy` **musi** iść
   pozycyjnie (po kolejności kolumn widoku) albo z jawnym aliasem — inaczej „column
   id does not exist".
2. **DELETE to OSOBNA ścieżka.** Funkcja upsertu używa `NEW.id`; na DELETE `NEW`
   jest NULL — `WHERE object_id_raw = NULL` nic nie skasuje (cichy staleness, nie
   błąd). Trigger DELETE woła osobną funkcję: `DELETE FROM bpp_rekord_mat WHERE id
   = ARRAY[ct, OLD.id]` (rekord; kaskada FK na autorzy) lub analogicznie na
   `bpp_autorzy_mat` (through-table). INSERT może współdzielić funkcję upsertu, DELETE — nie.
3. **Advisory lock: `SELECT … INTO STRICT`, nie gołe podzapytanie.**
   `pg_advisory_xact_lock` jest STRICT (`proisstrict=t`) → przy braku content_type
   `pg_advisory_xact_lock(NULL, NEW.id)` cicho nic nie blokuje (NULL, bez błędu);
   plpython V0 rzucał `IndexError`. Użyć `SELECT id INTO STRICT ct FROM
   django_content_type WHERE …` (rzuca `NO_DATA_FOUND`), by nie zgubić locka (#309).

**Status: do zrobienia.** PoC `ciagle` (rekord/UPDATE) zmierzony i dowiedziony
identyczny; ścieżki DELETE i `*_autorzy` do implementacji wg pułapek.

---

## 3. Zmiana 2 — bramka `WHEN` (lista kolumn) na UPDATE

**Co.** Rozbić złączony trigger: `INSERT OR DELETE` bezwarunkowe; `UPDATE` dostaje
`WHEN (<OLD.col IS DISTINCT FROM NEW.col OR …>)`, gdzie lista = kolumny bazowe
zasilające wyjście widoku. Trigger nie wchodzi, gdy żadna istotna kolumna się nie
zmieniła.

**Topologia i zasięg.** Wszystkie 5 tabel bazowych ma `bpp_*_cache_trigger`
(`AFTER INSERT OR UPDATE OR DELETE → bpp_refresh_cache`) — to bramkujemy/portujemy.
**Równolegle** wiszą triggery django-denorm `d_aft_row_*` → `denorm_dirtyinstance`.
Bramka `WHEN` dotyczy WYŁĄCZNIE cache-trigera (pomija odświeżenie `mat`); **nie
redukuje** kosztu enqueue denormu (`d_aft` strzela bezwarunkowo). Flush denormu
zapisuje wiersz bazowy → re-odpala zbramkowany cache-trigger (poprawnie — bramka
przepuszcza, bo zmieniła się kolumna na liście). Zysk bramki = „mniej jałowych
odświeżeń `mat`", nie „mniej fire'ów denormu".

**Lista kolumn — z `pg_depend`, nie z dopasowania nazw.** Widok dowolnie
transformuje kolumny: przemianowania (`wydawca_opis AS wydawnictwo` w
zwarte/doktorat/habilitacja), stałe-podzapytania (`(SELECT … 'pol.') AS jezyk_id`
w patencie), agregaty z joinu (`count(autor) AS liczba_autorow`). Dopasowanie po
nazwie gubiłoby `wydawca_opis` → cichy staleness pola `wydawnictwo` na 3 z 5 typów.
PostgreSQL rejestruje referowane kolumny bazowe w `pg_depend` (na poziomie kolumn,
przez regułę `_RETURN`) — źródło prawdy bez parsowania SQL:

```sql
SELECT a.attname
FROM pg_depend d
JOIN pg_rewrite r ON r.oid = d.objid
JOIN pg_class   v ON v.oid = r.ev_class
JOIN pg_attribute a ON a.attrelid = d.refobjid AND a.attnum = d.refobjsubid
WHERE v.relname = 'bpp_wydawnictwo_zwarte_view'              -- widok per-typ
  AND d.refobjid = 'bpp_wydawnictwo_zwarte'::regclass        -- TYLKO tabela bazowa
  AND d.classid = 'pg_rewrite'::regclass
  AND d.refclassid = 'pg_class'::regclass AND d.refobjsubid > 0;
```

`pg_depend` łapie kolumny referowane gdziekolwiek (SELECT/WHERE/JOIN/GROUP BY/ORDER
BY), gubi tylko nieużywane. Zweryfikowane: dla `zwarte` zawiera `wydawca_opis`; dla
`patent` pomija `jezyk_id`/`typ_kbn_id`/`charakter_formalny_id` (stałe-podzapytania)
i `liczba_autorow` (join). Z tego zbioru odejmujemy `{id, search_index,
tytul_oryginalny_sort}` (klucz; pochodne, których źródła i tak są w zbiorze).
**Doktorat/habilitacja:** ∪ `{autor_id, jednostka_id}` (zasilają widok `*_autorzy`).

**`ostatnio_zmieniony` zostaje na liście** (`auto_now`, w cache'u i w widoku) —
zero regresji semantyki „ostatnio zmienione". Zysk na churnie i tak zależy od
mechanizmu zapisu:

**Realny wzorzec zapisu — `opl_pub_*`** (jedyne potwierdzone pole niecached pisane
masowo). Bramka pomija zapis tylko, gdy nie bumpuje `ostatnio_zmieniony`:
- **pełny `save()`** (admin; `import_oplaty_publikacje[_alt].py`; normalizacja
  importu) → bumpuje `auto_now` → bramka **odpala** (słusznie — `ostatnio_zmieniony`
  realnie się zmienił);
- **targeted/wsadowe** → `auto_now` nie rusza → bramka **pomija**:
  `bulk_update(["opl_pub_cost_free"])` (`…ustaw_bezkosztowe.py:61`) i
  `save(update_fields=[5×opl_pub_*])` (`pbn_import/utils/fee_import.py:80`) — wsadowe
  (per-rok / batch) = realny zysk.

Mapowanie na benchmark: targeted/wsadowe = WC3 (skip); pełny save = WC1 (fire).
Bramka nie pomija edycji interaktywnych — i nie powinna.

**Kolejność termów `OR`** — kolumny tanie/fixed-width na początek (short-circuit),
duże typy (tekst/tablice/tsvector) na koniec.

**Kanarek (test) — OBOWIĄZKOWY.** Brak kolumny w `WHEN` zasilającej widok = cichy
staleness. Test: dla każdej tabeli zmień po kolei każdą kolumnę na wartość
zmieniającą wynik widoku, asercja `mat`/`autorzy_mat` == świeżo policzony z widoku.
Dwie zasady:
1. **Sklasyfikuj każdą kolumnę `mat`: synchroniczna-trigger / async-denorm / stała.**
   Pola async-denorm (`opis_bibliograficzny_cache`, `…_autorzy_cache`) i
   join-derived (`liczba_autorow` = `count(autor)`, nie kolumna bazowa) nie są
   odświeżane synchronicznie → przy natychmiastowej asercji dadzą fałszywy RED;
   testuj je **po `denorm.flush()`**, a join-derived ćwicz edycją tabeli through.
2. Skoro bramka pochodzi z `pg_depend`, drift „dodano kolumnę do widoku, zapomniano
   o bramce" znika — o ile generator-migracja jest re-uruchamiana przy zmianie
   widoku. Kanarek to backstop.

**Decyzja: lista-kolumn (VB/VD), z całowierszową (VA) jako fallback.** Lista (a)
łapie WC3, (b) tańsza (bez tsvectora). Całowierszowa `OLD.* IS DISTINCT FROM NEW.*`
kompiluje się na **wszystkich 5 tabelach** (mimo `hstore`/`tsvector`/`jsonb`) i jest
immune na pułapkę przemianowań — bezpieczny fallback, gdyby `pg_depend` okazał się
kłopotliwy dla któregoś typu (koszt: nie pomija WC3, płaci za tsvector).

**Warunek wdrożenia.** Najpierw **zmierzyć na produkcji** udział UPDATE-ów
no-op/non-cached (licznik `mat_writes`). Zysk pojawia się tylko na ścieżkach
nie-bumpujących `auto_now` (wsadowe `opl_pub_*`; jałowe re-zapisy denormu). Pytanie:
**wolumen ścieżek wsadowych/denorm vs interaktywnych** — do policzenia.

**Status: do zrobienia** (po Zmianie 1 i po pomiarze udziału skip).

---

## 4. Odrzucone alternatywy

- **Async „durable queue" (denorm `DirtyInstance`) zamiast synchronicznego
  triggera.** Oddaje gwarancję spójności transakcyjnej (strona rekordu, multiseek,
  **ewaluacja**); sprzęga poprawność cache'a z Celery; ewaluacja już spin-waituje
  na `DirtyInstance.count()==0`. Synchroniczny trigger to *feature*.
- **Selektywny UPDATE kolumn w funkcji** (zapisz tylko zmienione). Wolniejsze niż
  blankietowy `SELECT * z widoku`: MVCC i tak pisze pełną krotkę (1 vs 51 kolumn =
  ten sam heap-write); indeksy aktualizują się po *wartości*, nie po `SET`
  (blankietowy SET niezmienionych jest darmowy); i tak trzeba policzyć widok;
  dynamiczny `SET` → re-planowanie co fire (koszt eliminowany portem). „Nie zapisuj
  gdy nic się nie zmieniło" należy do bramki (§3) / `DO UPDATE … WHERE mat IS
  DISTINCT FROM EXCLUDED`, nie do selekcji kolumn.

---

## 5. Zastrzeżenia / co niezmierzone

- Benchmark na **PG18** (zrzut miał archiwum 1.16 → restore na psql-18; produkcja
  psql-16.13). Dla *względnego* porównania bez znaczenia.
- **Docker-on-Mac**: szum ~10–20%; `min` z prób; istotne duże skoki, nie różnice
  wewnątrz PL/Python.
- Zmierzono **tylko `ciagle`, tylko UPDATE**. Pozostałe typy + through-table idą tym
  samym wzorcem (z pułapkami §2).
- **Realny zysk bramki** = funkcja udziału ścieżek wsadowych/denorm — do zmierzenia
  przed Zmianą 2.
- **Podłoga ~0,29 ms/wiersz** (VC fire) to koszt `SELECT` z widoku (`count(autorzy)
  GROUP BY`). Atakuje to dopiero **statement-level + transition tables** (§1.6
  poprzedniego spec-u) — osobny, większy krok. **Statement-level jest
  NIEKOMPATYBILNE z bramką WHEN:** PG odrzuca `FOR EACH STATEMENT … WHEN (OLD.col …)`
  („warunek WHEN wyzwalacza instrukcji nie może wskazywać wartości kolumn").
  Przejście na statement-level likwiduje bramkę i przenosi filtr no-op do ciała
  funkcji (`WHERE old_tab.col IS DISTINCT FROM new_tab.col` na transition tables).
  Bramka per-wiersz i statement-level to rozłączne kierunki.

---

## 6. Plan wdrożenia (PR-y)

1. **PR „cache-trigger → PL/pgSQL"** — generator-migracja dla 8 triggerów (5 rekord
   + 3 autorzy), kanarek „mat == widok", benchmark VC vs V0 na zrzucie.
2. **PR „bramka WHEN"** — split INSERT/DELETE + UPDATE z listą-kolumn (`pg_depend`),
   kanarek rozszerzony o drift, **po** pomiarze udziału skip.

## 7. Ryzyka

- **7 migracji naprawczych** za obecnym triggerem (deadlocki 0310/0387, bug
  `autor_id`, bug podwójnej roli) → przepisanie wyłącznie za pełną suitą testów +
  kanarkiem; semantyka v3 portowana dokładnie.
- **Drift listy kolumn** → kanarek jako gate CI; generator re-uruchamiany przy
  zmianie widoku.

---

## Załącznik A — reprodukowalny harness + blueprint generatora (`ciagle`)

Kontener: `iplweb/bpp_dbserver:psql-18`, baza `bigprod` na schemacie v3.

```sql
-- pomiar: serwerowy czas + dowód skip/fire (mat_writes)
CREATE OR REPLACE FUNCTION bench_update(setclause text, n int)
RETURNS TABLE(ms numeric, mat_writes bigint) LANGUAGE plpgsql AS $$
DECLARE t0 timestamptz;
BEGIN
  t0 := clock_timestamp();
  EXECUTE format('UPDATE bpp_wydawnictwo_ciagle SET %s WHERE id IN '
    '(SELECT id FROM bpp_wydawnictwo_ciagle ORDER BY id LIMIT %s)', setclause, n);
  ms := round(extract(epoch from clock_timestamp()-t0)*1000,1);
  SELECT COALESCE(sum(n_tup_ins+n_tup_upd),0) INTO mat_writes
    FROM pg_stat_xact_user_tables WHERE relname='bpp_rekord_mat';
  RETURN NEXT;
END $$;
-- BEGIN; SELECT * FROM bench_update('punkty_kbn = punkty_kbn + 1', 2000); ROLLBACK;
```

**Config docelowy VD** (PL/pgSQL statyczny + bramka lista-kolumn), generowany z
katalogu — blueprint generator-migracji dla `ciagle`:

```sql
DO $gen$
DECLARE cols text; setc text; wc text;
BEGIN
  SELECT string_agg(quote_ident(column_name), ', ' ORDER BY ordinal_position) INTO cols
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='bpp_rekord_mat';
  SELECT string_agg(format('%I = EXCLUDED.%I', column_name, column_name), ', ') INTO setc
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='bpp_rekord_mat' AND column_name <> 'id';
  EXECUTE format($f$
    CREATE OR REPLACE FUNCTION bpp_refresh_rekord_ciagle() RETURNS trigger
    LANGUAGE plpgsql AS $body$
    DECLARE ct integer;
    BEGIN
      SELECT id INTO STRICT ct FROM django_content_type
        WHERE app_label=%L AND model=%L;            -- STRICT: głośny błąd, nie cichy no-op
      PERFORM pg_advisory_xact_lock(ct, NEW.id);
      INSERT INTO bpp_rekord_mat (%s)
      SELECT %s FROM bpp_wydawnictwo_ciagle_view WHERE object_id_raw = NEW.id
      ON CONFLICT (id) DO UPDATE SET %s;
      RETURN NULL;
    END $body$;
  $f$, 'bpp','wydawnictwo_ciagle', cols, cols, setc);

  -- bramka: kolumny bazowe zasilające widok — z pg_depend (NIE z dopasowania nazw:
  -- gubiłoby przemianowania jak wydawca_opis→wydawnictwo → cichy staleness).
  -- Tanie typy pierwsze; 'A' = tablice i tsvector do drogiego kubełka; -id, -pochodne.
  SELECT string_agg(format('OLD.%I IS DISTINCT FROM NEW.%I', a.attname, a.attname), ' OR '
           ORDER BY (t.typcategory IN ('S','A') OR a.atttypid='tsvector'::regtype)::int, a.attnum) INTO wc
    FROM pg_depend d
    JOIN pg_rewrite r ON r.oid = d.objid
    JOIN pg_class   v ON v.oid = r.ev_class AND v.relname = 'bpp_wydawnictwo_ciagle_view'
    JOIN pg_attribute a ON a.attrelid = d.refobjid AND a.attnum = d.refobjsubid
    JOIN pg_type     t ON t.oid = a.atttypid
    WHERE d.refobjid = 'bpp_wydawnictwo_ciagle'::regclass
      AND d.classid='pg_rewrite'::regclass AND d.refclassid='pg_class'::regclass
      AND d.refobjsubid > 0
      AND a.attname NOT IN ('id','search_index','tytul_oryginalny_sort');

  -- DELETE = OSOBNA funkcja (NEW jest NULL na DELETE)
  EXECUTE $d$
    CREATE OR REPLACE FUNCTION bpp_delete_rekord_ciagle() RETURNS trigger
    LANGUAGE plpgsql AS $b$ BEGIN
      DELETE FROM bpp_rekord_mat WHERE id = ARRAY[
        (SELECT id FROM django_content_type WHERE app_label='bpp' AND model='wydawnictwo_ciagle'),
        OLD.id]::integer[];  -- kaskada FK czyści bpp_autorzy_mat
      RETURN NULL; END $b$;
  $d$;
  EXECUTE 'DROP TRIGGER IF EXISTS bpp_wydawnictwo_ciagle_cache_trigger ON bpp_wydawnictwo_ciagle';
  EXECUTE 'CREATE TRIGGER bpp_wc_cache_ins AFTER INSERT ON bpp_wydawnictwo_ciagle '
          'FOR EACH ROW EXECUTE PROCEDURE bpp_refresh_rekord_ciagle()';
  EXECUTE 'CREATE TRIGGER bpp_wc_cache_del AFTER DELETE ON bpp_wydawnictwo_ciagle '
          'FOR EACH ROW EXECUTE PROCEDURE bpp_delete_rekord_ciagle()';
  EXECUTE format('CREATE TRIGGER bpp_wc_cache_upd AFTER UPDATE ON bpp_wydawnictwo_ciagle '
                 'FOR EACH ROW WHEN (%s) EXECUTE PROCEDURE bpp_refresh_rekord_ciagle()', wc);
END $gen$;
```

Dla pełnego portu: **through-table** (`*_autor`) — upsert filtrowany `object_id_raw
= NEW.rekord_id AND autor_id = NEW.autor_id`, DELETE po id wiersza; **doktorat/
habilitacja** — `wc` ∪ `{autor_id, jednostka_id}`, funkcja dodatkowo `DELETE+INSERT`
na `bpp_autorzy_mat`; **widoki `*_autorzy`** — `SELECT` **pozycyjnie** (kolumna
`"array"` w `bpp_praca_doktorska_autorzy`).
