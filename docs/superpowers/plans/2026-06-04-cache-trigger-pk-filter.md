# Optymalizacja triggera cache: filtr po surowym PK — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Przyspieszyć trigger `bpp_refresh_cache()` odświeżający `bpp_rekord_mat`
i `bpp_autorzy_mat`, zamieniając filtr po wyliczanej kolumnie-tablicy (`Seq Scan`
+ drogie planowanie 5-gałęziowej unii) na filtr po surowym, indeksowanym PK
tabeli bazowej (`Index Cond` seek), bez zmiany zawartości cache.

**Architecture:** Do każdego z 10 widoków per-typ (`*_view`, `*_autorzy`)
doklejamy przez `CREATE OR REPLACE VIEW` skalarną kolumnę `object_id_raw`
(= PK publikacji). Przepisujemy funkcję `bpp_refresh_cache()` tak, by SELECT-em
źródłowym celowała w konkretny widok per-typ (wg `TD["table_name"]`) i filtrowała
po `object_id_raw`. Operacje na mat-tabelach (DELETE / `ON CONFLICT (id)`)
zostają na indeksowanej tablicy `id`. `bpp_rekord` / `bpp_autorzy` / mat-tabele
/ widoki zależne pozostają nietknięte (brak `DROP … CASCADE`).

**Tech Stack:** PostgreSQL, plpython3u, Django migrations (RunPython +
`load_custom_sql`), pytest + model_bakery.

**Powiązane issues:** #311 (ta optymalizacja), #309 (niedeterministyczny advisory
lock — domykany przy okazji rewrite'u funkcji).

---

## Kontekst i dowody (dlaczego)

Trigger jest `FOR EACH ROW` na 8 tabelach (5 publikacji + 3 `*_autor`), wszystkie
wołają `bpp_refresh_cache()` (plpython3u). Najnowsza wersja funkcji:
`src/bpp/migrations/0399_fix_refresh_cache_upsert.sql`. Funkcja dla
zmienionego rekordu robi upsert do mat-tabel selektem:

```sql
SELECT ... FROM bpp_rekord  WHERE id = ARRAY[ct, obj]::INTEGER[2]
SELECT ... FROM bpp_autorzy WHERE id = ARRAY[ct, obj]::INTEGER[2] [AND autor_id = X]
```

`bpp_rekord`/`bpp_autorzy` = `UNION ALL` 5 pod-widoków; `id` = `ARRAY[(SELECT ct…),
tabela.id]`. PostgreSQL nie rozkłada `array_eq` na `tabela.id = obj`, więc:

- predykat ląduje jako `Filter`, nie `Index Cond` → **Seq Scan** tabel bazowych,
- skanowane są **wszystkie 5 gałęzi** (ct to InitPlan, nieznany statycznie),
- drogie **planowanie** unii, powtarzane przy każdym `plpy.execute`.

**EXPLAIN ANALYZE na realnym dumpie produkcyjnym (~2 tys. rekordów):**

| | Obecnie (`bpp_rekord` WHERE id = ARRAY[6,830]) | Po (`*_view` WHERE object_id_raw = 830) |
|---|---|---|
| Dostęp do tabeli | `Seq Scan` 1658 wierszy | `Index Cond: (id = 830)` |
| Planning Time | 22,6 ms | 2,5 ms |
| Execution Time | 2,3 ms | 0,2 ms |

Część wykonawcza skaluje się z rozmiarem tabeli → na produkcji (100k+) przewaga
rośnie liniowo.

**Potwierdzenie kwalifikowalności indeksu (`enable_seqscan=off`, niezależne od
liczby wierszy):** `id = ARRAY[…]` → `Filter`; `(id)[2] = obj` → `Filter`
(Postgres nie zwija subskryptu konstruktora tablicy); `surowa_kolumna = obj` →
`Index Cond`. Jedyne wyjście: filtr po realnej skalarnej kolumnie = PK bazowy.

**Weryfikacja, że `CREATE OR REPLACE VIEW` z dokejoną kolumną nie psuje zależnych
`SELECT *`:** sprawdzone empirycznie — widok zależny zachowuje zamrożoną listę
kolumn, mat-tabela (snapshot) nietknięta.

---

## Mapowanie trigger → widok per-typ → surowy PK

| Tabela triggera | Odśwież | Widok rekordu | Widok autorów | `object_id_raw` ze źródła |
|---|---|---|---|---|
| `bpp_wydawnictwo_ciagle` | rekord+autorzy | `bpp_wydawnictwo_ciagle_view` | `bpp_wydawnictwo_ciagle_autorzy` | `…ciagle.id` / `…ciagle_autor.rekord_id` |
| `bpp_wydawnictwo_ciagle_autor` | autorzy | — | `bpp_wydawnictwo_ciagle_autorzy` | `…ciagle_autor.rekord_id` |
| `bpp_wydawnictwo_zwarte` | rekord+autorzy | `bpp_wydawnictwo_zwarte_view` | `bpp_wydawnictwo_zwarte_autorzy` | `…zwarte.id` / `…zwarte_autor.rekord_id` |
| `bpp_wydawnictwo_zwarte_autor` | autorzy | — | `bpp_wydawnictwo_zwarte_autorzy` | `…zwarte_autor.rekord_id` |
| `bpp_patent` | rekord+autorzy | `bpp_patent_view` | `bpp_patent_autorzy` | `…patent.id` / `…patent_autor.rekord_id` |
| `bpp_patent_autor` | autorzy | — | `bpp_patent_autorzy` | `…patent_autor.rekord_id` |
| `bpp_praca_doktorska` | rekord+autorzy | `bpp_praca_doktorska_view` | `bpp_praca_doktorska_autorzy` | `…doktorska.id` |
| `bpp_praca_habilitacyjna` | rekord+autorzy | `bpp_praca_habilitacyjna_view` | `bpp_praca_habilitacyjna_autorzy` | `…habilitacyjna.id` |

Widoki autorów through-table (`ciagle/zwarte/patent_autorzy`) wystawiają
`object_id_raw = <tabela>_autor.rekord_id` (indeks na `rekord_id` istnieje).
Widoki doktorat/habilitacja (`FROM praca…, bpp_autor`) wystawiają
`object_id_raw = praca….id` (PK). `autor_id` we wszystkich jest realną kolumną.

---

## File Structure

- **Create** `src/bpp/migrations/0421_cache_trigger_pk_filter.sql` — 10×
  `CREATE OR REPLACE VIEW` (dokejona `object_id_raw`) + `CREATE OR REPLACE
  FUNCTION bpp_refresh_cache()` (routing + filtr po `object_id_raw` +
  deterministyczny advisory lock).
- **Create** `src/bpp/migrations/0421_cache_trigger_pk_filter.py` — `RunPython`
  ładujący SQL przez `load_custom_sql` (wzorzec jak `0418_*`), `dependencies =
  [("bpp", "0420_autor_pokazuj_siec_powiazan_and_more")]`, reverse = przywrócenie
  poprzednich definicji (lub `noop` z komentarzem — patrz Task 4).
- **Create/Modify test** `src/bpp/tests/test_cache/test_cache_pk_filter.py` —
  testy poprawności (treść cache identyczna) + obecność `object_id_raw`.
- Widoki bazowe generujemy z **żywej bazy** (`pg_get_viewdef`, stan po 0420),
  doklejając kolumnę przed głównym `FROM` — to ground truth, bezpieczniejsze niż
  ręczne przepisywanie 660 linii DDL.

---

## Task 1: Wygeneruj SQL widoków per-typ z dokejoną `object_id_raw`

**Files:**
- Create: `src/bpp/migrations/0421_cache_trigger_pk_filter.sql` (część widokowa)

- [ ] **Step 1: Wyciągnij definicje 10 widoków z żywej bazy i dokej kolumnę.**

Dla każdego widoku: `pg_get_viewdef(<view>, true)`, wstaw `, <raw_expr> AS
object_id_raw` bezpośrednio przed pierwszą linią `^   FROM ` (3 spacje = główny
FROM; subzapytania są głębiej wcięte), owiń w `CREATE OR REPLACE VIEW <view> AS
… ;`. Mapowanie `raw_expr` jak w tabeli wyżej. Skrypt pomocniczy
(uruchom przy podłączonym `run-site`):

```bash
PG_PORT=$(cat .dev_helpers_pg_port); export PGPASSWORD=password
PSQL="psql -h localhost -p $PG_PORT -U bpp -d bpp -X -tA"
emit() { # $1=view $2=raw_expr
  echo "CREATE OR REPLACE VIEW $1 AS"
  $PSQL -c "SELECT pg_get_viewdef('$1'::regclass, true);" \
    | awk -v raw="$2" '/^   FROM / && !d {print "    , " raw " AS object_id_raw"; d=1} {print}'
  echo ";"
  echo
}
{
  emit bpp_wydawnictwo_ciagle_view          bpp_wydawnictwo_ciagle.id
  emit bpp_wydawnictwo_zwarte_view          bpp_wydawnictwo_zwarte.id
  emit bpp_patent_view                      bpp_patent.id
  emit bpp_praca_doktorska_view             bpp_praca_doktorska.id
  emit bpp_praca_habilitacyjna_view         bpp_praca_habilitacyjna.id
  emit bpp_wydawnictwo_ciagle_autorzy       bpp_wydawnictwo_ciagle_autor.rekord_id
  emit bpp_wydawnictwo_zwarte_autorzy       bpp_wydawnictwo_zwarte_autor.rekord_id
  emit bpp_patent_autorzy                   bpp_patent_autor.rekord_id
  emit bpp_praca_doktorska_autorzy          bpp_praca_doktorska.id
  emit bpp_praca_habilitacyjna_autorzy      bpp_praca_habilitacyjna.id
} > /tmp/views_part.sql
```

- [ ] **Step 2: Zweryfikuj składnię (apply + rollback w transakcji).**

```bash
( echo "BEGIN;"; cat /tmp/views_part.sql; echo "ROLLBACK;" ) \
  | psql -h localhost -p "$PG_PORT" -U bpp -d bpp -X -v ON_ERROR_STOP=1
```
Expected: brak błędów (ROLLBACK na końcu). Jeśli któryś widok ma główny `FROM`
z innym wcięciem niż 3 spacje — popraw `awk` i ponów.

- [ ] **Step 3: Potwierdź seek dla wariantu zoptymalizowanego.**

```bash
( echo "BEGIN;"; cat /tmp/views_part.sql;
  echo "EXPLAIN SELECT * FROM bpp_wydawnictwo_ciagle_view WHERE object_id_raw = 830;";
  echo "ROLLBACK;" ) | psql -h localhost -p "$PG_PORT" -U bpp -d bpp -X | grep -i "Index Cond"
```
Expected: `Index Cond: (id = 830)`.

## Task 2: Przepisz funkcję `bpp_refresh_cache()`

**Files:**
- Modify: `src/bpp/migrations/0421_cache_trigger_pk_filter.sql` (część funkcji)

- [ ] **Step 1: Dopisz `CREATE OR REPLACE FUNCTION` z routingiem.** Kluczowe
  różnice względem `0399`:
  - jawny słownik routingu `TABLE → (pub_base, is_through)`,
  - źródłowy SELECT z widoku per-typ: `… FROM {pub_base}_view WHERE object_id_raw
    = {object_id}` (rekord) oraz `… FROM {pub_base}_autorzy WHERE object_id_raw =
    {object_id} [AND autor_id = {autor_id}]` (autorzy),
  - filtr mat-tabel (DELETE / ON CONFLICT) **bez zmian** — `id`/`rekord_id =
    ARRAY[ct,obj]`,
  - advisory lock: `plpy.execute("SELECT pg_advisory_xact_lock(%s, %s)",
    [content_type_id, object_id])` (domyka #309),
  - `content_type_id` liczony dla `pub_base` (nie dla modelu `*_autor`).

Pełny szkielet funkcji w sekcji „Szkielet funkcji" poniżej.

- [ ] **Step 2: Dopisz część funkcji do pliku `.sql`** (po części widokowej),
  całość owinięta w `BEGIN; … COMMIT;`.

## Task 3: Migracja `.py`

**Files:**
- Create: `src/bpp/migrations/0421_cache_trigger_pk_filter.py`

- [ ] **Step 1: Napisz migrację wzorem `0418_autor_dyscyplina_trigger_on_conflict.py`.**

```python
from pathlib import Path
from django.db import connection, migrations


def load_sql(apps, schema_editor):
    sql_file = Path(__file__).parent / "0421_cache_trigger_pk_filter.sql"
    with open(sql_file) as f:
        sql = f.read()
    with connection.cursor() as cursor:
        cursor.execute(sql)


class Migration(migrations.Migration):
    dependencies = [
        ("bpp", "0420_autor_pokazuj_siec_powiazan_and_more"),
    ]
    operations = [
        migrations.RunPython(load_sql, migrations.RunPython.noop),
    ]
```

- [ ] **Step 2: Uruchom migrację na żywej bazie i sprawdź brak błędów.**

Run: `uv run python src/manage.py migrate bpp` (przy działającym `run-site`
wskaż jego port przez zmienne — albo odpal w ramach pytest/testcontainers).
Expected: `Applying bpp.0421_cache_trigger_pk_filter… OK`.

## Task 4: Testy poprawności (cache niezmieniony)

**Files:**
- Create: `src/bpp/tests/test_cache/test_cache_pk_filter.py`

- [ ] **Step 1: Test — `object_id_raw` istnieje i daje seek.**

```python
import pytest
from django.db import connection


@pytest.mark.django_db
def test_object_id_raw_present_on_views():
    views = [
        "bpp_wydawnictwo_ciagle_view", "bpp_wydawnictwo_zwarte_view",
        "bpp_patent_view", "bpp_praca_doktorska_view",
        "bpp_praca_habilitacyjna_view", "bpp_wydawnictwo_ciagle_autorzy",
        "bpp_wydawnictwo_zwarte_autorzy", "bpp_patent_autorzy",
        "bpp_praca_doktorska_autorzy", "bpp_praca_habilitacyjna_autorzy",
    ]
    with connection.cursor() as c:
        for v in views:
            c.execute(
                "SELECT 1 FROM information_schema.columns "
                "WHERE table_name=%s AND column_name='object_id_raw'", [v])
            assert c.fetchone(), f"{v} nie ma object_id_raw"
```

- [ ] **Step 2: Test — edycja publikacji aktualizuje `bpp_rekord_mat` (treść).**

```python
from model_bakery import baker
from bpp.models import Rekord, Wydawnictwo_Ciagle


@pytest.mark.django_db
def test_edit_refreshes_rekord_mat():
    w = baker.make(Wydawnictwo_Ciagle, tytul_oryginalny="STARY")
    w.tytul_oryginalny = "NOWY TYTUL"
    w.save()
    assert Rekord.objects.get_for_model(w).tytul_oryginalny == "NOWY TYTUL"
```

- [ ] **Step 3: Test — dodanie/edycja autora aktualizuje `bpp_autorzy_mat`.**

```python
from bpp.models import Autor, Jednostka


@pytest.mark.django_db
def test_author_change_refreshes_autorzy_mat():
    w = baker.make(Wydawnictwo_Ciagle)
    a = baker.make(Autor)
    j = baker.make(Jednostka)
    w.dodaj_autora(a, j)
    rec = Rekord.objects.get_for_model(w)
    assert rec.autorzy_set.filter(autor=a).exists()
```

- [ ] **Step 4: Uruchom istniejące + nowe testy cache.**

Run: `uv run pytest src/bpp/tests/test_cache/ -q`
Expected: PASS (istniejące testy cache to siatka bezpieczeństwa — zachowanie
musi być identyczne).

## Task 5: Weryfikacja i commit

- [ ] **Step 1: `ruff check` / `ruff format` na zmienionych plikach `.py`.**
- [ ] **Step 2: Pełny przebieg `test_cache` + smoke kilku testów multiseek
  (które czytają `bpp_rekord_mat`).**
- [ ] **Step 3: Commit** (`feat(cache): filtr triggera po surowym PK …`,
  `Closes #311`, `Closes #309`).

---

## Szkielet funkcji `bpp_refresh_cache()`

```python
table_name = TD["table_name"]
event = TD["event"]
field = "old" if event in ("DELETE", "UPDATE") else "new"

# routing: tabela triggera -> (bazowa tabela publikacji, czy to through-table autorow)
ROUTING = {
    "bpp_wydawnictwo_ciagle":       ("bpp_wydawnictwo_ciagle", False),
    "bpp_wydawnictwo_ciagle_autor": ("bpp_wydawnictwo_ciagle", True),
    "bpp_wydawnictwo_zwarte":       ("bpp_wydawnictwo_zwarte", False),
    "bpp_wydawnictwo_zwarte_autor": ("bpp_wydawnictwo_zwarte", True),
    "bpp_patent":                   ("bpp_patent", False),
    "bpp_patent_autor":             ("bpp_patent", True),
    "bpp_praca_doktorska":          ("bpp_praca_doktorska", False),
    "bpp_praca_habilitacyjna":      ("bpp_praca_habilitacyjna", False),
}
pub_base, is_through = ROUTING[table_name]
model_name = pub_base.split("_", 1)[1]          # np. 'wydawnictwo_ciagle'
app_name = pub_base.split("_", 1)[0]            # 'bpp'

# object_id = PK publikacji
object_id = TD[field]["rekord_id"] if is_through else TD[field]["id"]

# content_type_id (cache w GD jak w 0399)
cache_key = "django_content_type_ver_2"
if GD.get(cache_key) is None:
    GD[cache_key] = {}
if pub_base not in GD[cache_key]:
    r = plpy.execute(
        "SELECT id FROM django_content_type "
        "WHERE app_label = '%s' AND model = '%s'" % (app_name, model_name))
    GD[cache_key][pub_base] = r[0]["id"]
content_type_id = GD[cache_key][pub_base]

# co odświeżamy
refresh_rekord = not is_through
refresh_autor = True            # publikacje: tak; through: tak (tylko autorzy)

rekord_view = pub_base + "_view"
autorzy_view = pub_base + "_autorzy"

# filtr autora przy edycji wiersza *_autor — nie przeliczaj wszystkich autorow
autor_extra = ""
if is_through:
    autor_extra = " AND autor_id = %s" % TD[field]["autor_id"]

mat_id_arr = "ARRAY[%s, %s]::INTEGER[2]" % (content_type_id, object_id)

# kolumny mat-tabel z cache (jak 0399) -> get_table_columns()
# ... (bez zmian względem 0399: dynamiczna lista kolumn + ON CONFLICT (id))

plpy.execute("SELECT pg_advisory_xact_lock(%s, %s)",
             [content_type_id, object_id])   # deterministyczny lock (domyka #309)

with plpy.subtransaction():
    if refresh_rekord:
        # DELETE FROM bpp_rekord_mat WHERE id = <mat_id_arr>
        # if not DELETE: INSERT INTO bpp_rekord_mat (<cols>)
        #   SELECT <cols> FROM {rekord_view} WHERE object_id_raw = {object_id}
        #   ON CONFLICT (id) DO UPDATE SET <set>
        # (DELETE bpp_rekord_mat kaskaduje na bpp_autorzy_mat — patrz 0399)
        ...
    if refresh_autor:
        # DELETE FROM bpp_autorzy_mat WHERE rekord_id = <mat_id_arr> {autor_extra}
        # if not DELETE: INSERT INTO bpp_autorzy_mat (<cols>)
        #   SELECT <cols> FROM {autorzy_view}
        #   WHERE object_id_raw = {object_id} {autor_extra}
        #   ON CONFLICT (id) DO UPDATE SET <set>
        ...
```

Uwaga: zachowujemy logikę „DELETE rekordu kaskaduje na autorzy_mat (FK), więc po
odświeżeniu rekordu odświeżamy też autorzy" z `0399`. Część budująca dynamiczną
listę kolumn, `ON CONFLICT (id)` i `plpy.subtransaction()` przenosimy z `0399`
bez zmian — różni się **tylko** klauzula źródłowa (`FROM … WHERE object_id_raw`)
i klucz advisory lock.

## Reverse migracji

`RunPython.noop` jako reverse jest akceptowalne (forward jest idempotentny —
`CREATE OR REPLACE`), ALE czystszy reverse to ponowne załadowanie poprzednich
definicji: `load_custom_sql("0403_autorzy_ostatnio_zmieniony")`,
`load_custom_sql("0402_autorzy_data_oswiadczenia")`,
`load_custom_sql("0399_fix_refresh_cache_upsert")`. Wybór: **noop + komentarz**
(views per-typ z `object_id_raw` są nieszkodliwe wstecznie, a stара funkcja i tak
zostałaby nadpisana forwardem) — chyba że review wymaga pełnego rollbacku.
```
