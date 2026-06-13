# Spec: pożegnanie z PL/Python — likwidacja `plpython3u` z obrazu (czerwiec 2026)

Cel: usunąć rozszerzenie `plpython3u` z obrazu `iplweb/bpp_dbserver`, przepisując
lub eliminując wszystkie funkcje PL/Python. Korzyści: lżejszy obraz, koniec
**untrusted** języka (mniejsza powierzchnia bezpieczeństwa), zgodność z
managed-Postgres (RDS/Cloud SQL nie dają `plpython3u`).

**Zależność:** największa i najtrudniejsza funkcja — `bpp_refresh_cache` — ma
własny spec ([spec-bpp-refresh-cache-plpgsql-2026-06.md](spec-bpp-refresh-cache-plpgsql-2026-06.md),
port + bramka + benchmark). Ten dokument obejmuje **pozostałe 8** funkcji oraz
końcowe `DROP EXTENSION` + zmianę obrazu. Finalny `DROP EXTENSION` wymaga, by
Spec 1 był już wdrożony (refresh_cache nie może zostać jako plpython).

---

## Inwentarz 9 funkcji PL/Python i ich los

Charakterystyka z `pg_proc.prosrc` (żywa baza). Sesyjnego stanu `GD` (brak
odpowiednika w plpgsql) używają **tylko** `bpp_refresh_cache` i `trigger_tytul_sort`
— **pozostałe 7 jest GD-free → port mechaniczny**.

| Funkcja | Trigger na | Co robi | Los |
|---|---|---|---|
| `bpp_refresh_cache` | 5 tabel publikacji + 3× `*_autor` | cache `bpp_rekord_mat`/`autorzy_mat` (`GD`) | **Spec 1** (port plpgsql) |
| `trigger_tytul_sort` | 5 tabel publikacji (BEFORE) | klucz sortu tytułu (`GD`) | **eliminacja** (§2) |
| `bpp_autor_dyscyplina_change` | `bpp_autor_dyscyplina` (UPDATE) | dirty-marker denorm (filtr rok+dyscyplina) | port plpgsql (§1) |
| `bpp_autor_dyscyplina_delete` | `bpp_autor_dyscyplina` (DELETE) | dirty-marker denorm (filtr rok+dyscyplina) | port plpgsql (§1) |
| `bpp_autor_dyscyplina_rozne` | `bpp_autor_dyscyplina` (INS/UPD) | walidacja: dyscyplina ≠ subdyscyplina | port plpgsql (§1) |
| `bpp_autor_ustaw_jednostka_aktualna` | (autor↔jednostka) | aktualna jednostka (`plpy.prepare`) | port plpgsql (§1) |
| `bpp_jednostka_ustaw_wydzial_aktualna` | (jednostka↔wydział) | aktualny wydział (`plpy.prepare`) | port plpgsql (§1) |
| `bpp_jednostka_sprawdz_uczelnia_id` | `bpp_jednostka` | walidacja `uczelnia_id` | port plpgsql (§1) |
| `bpp_jednostka_wydzial_sprawdz_uczelnia_id` | (jednostka_wydział) | walidacja `uczelnia_id` | port plpgsql (§1) |

**Bilans:** 1 (Spec 1) + **7 do portu (tu)** + 1 wyeliminowany.

---

## 1. Port 7 funkcji na PL/pgSQL (mechaniczny)

Wszystkie 7 jest GD-free. Trzy grupy:

### 1a. Dwa dirty-markery denorm (`bpp_autor_dyscyplina_change`/`_delete`)
Gdy autorowi zmienia/usuwa się przypisanie dyscypliny na dany rok
(`bpp_autor_dyscyplina`), znajdują **dotknięte publikacje** (ciagle/zwarte/patent,
gdzie ten autor w tym roku miał starą/nową dyscyplinę) i robią
`INSERT INTO denorm_dirtyinstance(content_type_id, object_id) SELECT …`, żeby
denorm je przeliczył. `change` ma guard: zmiana `rok`/`autor_id` →
`plpy.error` (do `RAISE EXCEPTION`).

**Dlaczego ręczne, nie denorm `@depend_on_related`:** to propagacja **filtrowana**
(rok + dyscyplina + ten autor), a `@depend_on_related` oznaczyłoby wszystkie
powiązane wiersze. To jedyne **2** funkcje (z 125 piszących do
`denorm_dirtyinstance`) NIE-generowane przez denorm — pozostałe 123 to
auto-generowane `f_d_aft_row_*` (już plpgsql). Czyli po porcie tych 2 całe
dirty-markowanie jest w plpgsql.

**Port:** zwykły `EXECUTE`/`INSERT … SELECT` (pętla po 3 typach + `content_type_id`
z `SELECT … INTO`). Można uprościć temp-table do CTE. Bez GD, bez stanu.

### 1b. Dwa „ustaw aktualną" (`bpp_autor_ustaw_jednostka_aktualna`, `bpp_jednostka_ustaw_wydzial_aktualna`)
Utrzymują denormalizowane „aktualna jednostka"/„aktualny wydział". Używają
`plpy.prepare` → **portuje się natywnie** (plpgsql i tak cache'uje plany
przygotowanych zapytań); ciało to kilka `SELECT`/`UPDATE`.

### 1c. Trzy walidatory (`assert`→`RAISE EXCEPTION`)
- `bpp_autor_dyscyplina_rozne` (3 linie): `IF NEW.dyscyplina_naukowa_id =
  NEW.subdyscyplina_naukowa_id THEN RAISE EXCEPTION 'Dyscypliny muszą być różne'`.
- `bpp_jednostka_sprawdz_uczelnia_id`, `bpp_jednostka_wydzial_sprawdz_uczelnia_id`:
  walidacja spójności `uczelnia_id` (cross-row → nie da się CHECK-iem, stąd
  trigger) → `RAISE EXCEPTION`.

**Status: do zrobienia** (niezależne od Spec 1; można równolegle).

---

## 2. `trigger_tytul_sort` — eliminacja, nie port

Wszystkie zapisy `tytul_oryginalny` idą przez ORM, więc gwarancja triggera DB
(łapanie zapisów spoza ORM) jest zbędna — klucz sortu liczymy w warstwie modelu.
`trigger_tytul_sort` obcina rodzajniki na początku tytułu per język (sztywna
tablica: ang. `the/a`, niem. `der/die/das`, fr. `la/le/en`, wł., hiszp.; domyślnie
pol. = bez obcinania).

**Rekomendacja — (A) override `save()`** w abstrakcyjnym `DwaTytuly`
(`abstract/naming.py`, gdzie już jest hook `safe_html(tytul_oryginalny)`): policz
`tytul_oryginalny_sort` obok i dorzuć go do `update_fields`, gdy `tytul_oryginalny`
jest w `update_fields` (jedyny gotcha). Synchroniczne, zero infry.

**Alternatywa — (B) pole `@denormalized`** zależne od `tytul_oryginalny`/`jezyk_id`:
wpina się w istniejący flush denorm (rekompilacja dokleja się do zapisu, który i
tak się dzieje; brak gotcha z `update_fields`), kosztem eventual-consistency klucza
(akceptowalne — jak `opis_bibliograficzny_cache`).

Logika obcinania → funkcja Pythona; opcjonalnie przedrostki w tabeli słownikowej
(edytowalne bez migracji). PG **nie ma kolacji „ignoruj rodzajnik"** (to katalogowe
*nonfiling characters*, spoza Unicode Collation Algorithm — ICU umie ignorować
interpunkcję przez `alternate=shifted`, ale nie słowa), więc osobna kolumna-klucz
`tytul_oryginalny_sort` to właściwy, standardowy wzorzec — zostaje, zmienia się
tylko miejsce liczenia.

**Status: do zrobienia** (niezależne od Spec 1).

---

## 3. Sekwencja `DROP EXTENSION` + obraz (KRYTYCZNE)

Projekt używa `django-pg-baseline`: świeże bazy ładują `baseline-sql/baseline.sql`,
potem TYLKO migracje po punkcie baseline — **stare migracje tworzące funkcje
plpython NIE są odgrywane na świeżych instalacjach**. Dlatego:

1. Migracje: `CREATE OR REPLACE` **8 funkcji** w PL/pgSQL (`bpp_refresh_cache` ze
   Spec 1 + 7 z §1) oraz `DROP TRIGGER`+`DROP FUNCTION trigger_tytul_sort` (logika
   → save()/denorm, §2).
2. Migracja `DROP EXTENSION plpython3u` — możliwa dopiero gdy zero zależnych
   obiektów (po pkt 1, **w tym Spec 1**).
3. **Refresh baseline** (`baseline.sql` regenerowany → wersje PL/pgSQL, bez
   `CREATE EXTENSION plpython3u`).
4. Dopiero **potem** usunięcie `plpython3u` z obrazu (osobne repo
   [iplweb/bpp-dbserver](https://github.com/iplweb/bpp-dbserver)) + aktualizacja
   noty w `src/django_bpp/settings/base.py:502` („Our image has plpython3u…").

**Koordynacja obrazu.** Obraz MUSI zachować `plpython3u`, dopóki jakakolwiek
wdrożona baza może mieć funkcje plpython (aż migracja DROP z pkt 2 przejdzie
wszędzie). Dodatkowo `PG_BASELINE["REBUILD_IMAGE"]` (= `iplweb/bpp_dbserver:
psql-16.13`) służy do refreshu baseline (pkt 3), który odgrywa migracje od starego
punktu baseline (a `baseline.sql` ma `CREATE EXTENSION plpython3u` + odwołania) —
więc REBUILD_IMAGE musi mieć plpython **aż do refreshu włącznie**. Migracje
port+DROP muszą wejść **przed** nowym punktem baseline; dopiero gdy zregenerowany
`baseline.sql` jest plpython-free, można zdjąć plpython z obrazu. Kolejność:
**port (Spec 1 + §1 + §2) → deploy → DROP EXTENSION → refresh baseline → obraz bez
plpython**.

---

## 4. Plan wdrożenia (PR-y)

1. **PR „port 7 plpython → plpgsql"** — §1 (2 dirty-markery, 2 setters, 3
   walidatory). Niezależny od Spec 1; równolegle.
2. **PR „eliminacja trigger_tytul_sort"** — §2 (save()-hook lub denorm + backfill +
   `DROP TRIGGER/FUNCTION`).
3. **PR „DROP plpython3u"** — po wdrożeniu Spec 1 + PR 1–2: migracja `DROP
   EXTENSION` + refresh baseline. **Osobno** koordynowana zmiana obrazu
   `bpp-dbserver` (po deployu DROP-a).

## 5. Ryzyka

- **Sekwencja plpython/baseline/obraz** — `DROP` dopiero gdy wszystkie 9 funkcji
  są plpgsql/wyeliminowane (w tym `bpp_refresh_cache` ze Spec 1); obraz i
  REBUILD_IMAGE tracą plpython jako ostatnie, po refreshu baseline.
- **Dirty-markery dyscyplin** — port musi zachować **filtr rok+dyscyplina** (nie
  oznaczać wszystkich publikacji autora) i guard zmiany `rok`/`autor_id`; pełna
  suita testów + sprawdzenie, że `denorm_dirtyinstance` dostaje te same wiersze co
  przed portem.
- **Walidatory `uczelnia_id`** — to integralność cross-row; po porcie potwierdzić,
  że nadal blokują niespójne zapisy (test reprodukujący).
