# HANDOFF: dokończyć pomiar czasów wydajności (drugi komputer)

**Data:** 2026-08-07
**Gałąź:** `django-6.1`
**Powód handoffu:** host `mac-mini` jest stale obłożony (równolegle biegną
inne sesje i suity testowe), więc **nie da się na nim zmierzyć czasów
odpowiedzi**. Liczby zapytań są już zmierzone i pewne — brakuje wyłącznie
wiarygodnych czasów ściany.

---

## Co jest ZROBIONE (nie powtarzaj)

Audyt Django 6.1 pod kątem wydajności + cztery naprawione defekty.
Pełny raport: `AUDYT-DJANGO-6.1-WYDAJNOSC.md` (nietrackowany, w korzeniu
worktree `bpp-django-6.1`).

### Ustalenia, które są już pewne

1. **Sam upgrade do Django 6.1 nie przyspiesza niczego.** Liczby zapytań
   bit w bit identyczne jak na 5.2 we wszystkich 15 scenariuszach, w obu
   wariantach konfiguracji cache. Zero regresji — i zero zysku.
2. Zysk wymaga jawnego opt-inu w *fetch modes*
   (`QuerySet.fetch_mode(FETCH_PEERS)`).
3. Najcenniejsze w 6.1 jest `FETCH_RAISE`/własny `FetchMode` jako
   **detektor N+1**. Tym mechanizmem znalazłem cztery defekty, których nie
   widać w kodzie.

### Wdrożone poprawki

Na `dev` (Django 5.2, wypchnięte):

| commit | co |
|---|---|
| `f509c7bdc` | filtr „Wydział" na `/admin/bpp/autor/` listował **504 jednostki zamiast 7** (bug UI, nie tylko koszt) |
| `5ffc83f50` | `JednostkaFilter` bez `select_related("uczelnia")`; `LogEntryFilterBase.only()` bez `last_name`/`first_name` |
| `6416e2ac0` | indeks jednostek: `.count()` na relacji odwrotnej 3–4× na wiersz → `annotate()` |

Na `django-6.1`:

| commit | co |
|---|---|
| `ccb9756ff` | PR #733 (squash): `FETCH_PEERS` w `BaseBppAdminMixin` — **wymaga 6.1** |

### Zmierzone liczby zapytań (pewne, powtórzone w 5 przebiegach)

Konfiguracja z produkcyjnymi regułami `CACHEOPS`:

```
scenariusz                        przed    po
publiczne: lista jednostek          514     3
admin: wyd. ciągłe (changelist)     190    34
admin: wyd. zwarte (changelist)     220    36
admin: jednostka (changelist)        66    17
admin: autor (changelist)            27    27   (spadły round-tripy do Redisa, nie SQL)
admin: źródło (changelist)           16    16   ← KONTROLER, nietknięty
pozostałe 9 scenariuszy        bez zmian
```

### Testy

* `django-6.1` (po mergu #733): `1016 passed, 1 skipped`
* `dev` (Django 5.2): `1012 passed, 1 skipped`
  (różnica = 4 testy `test_fetch_peers.py`, które żyją tylko na 6.1)

Zakres: `src/bpp/tests/test_admin/` + `src/bpp/tests/test_views/`.

---

## Co ZOSTAŁO do zrobienia

**Jedno zadanie: zmierzyć czasy odpowiedzi na cichym hoście.**

Dotychczasowe pomiary czasu są niewiarygodne i **nie wolno ich cytować jako
wyniku**. Dowód: scenariusz kontrolny `admin: źródło (changelist)` ma te
same 16 zapytań przed i po wszystkich zmianach (żadna go nie dotyka), a
zmierzony czas skakał **320 → 420 ms**. Skoro niezmieniona ścieżka kodu daje
+100 ms, to różnice czasowe pochodzą z obciążenia hosta, nie z kodu. Prawie
każdy pomiar dostawał flagę `SZUM` (odchylenie > 10% mediany).

Liczby czasowe, które trafiły do wiadomości commitów i do opisu PR #733
(np. „185 → 120 ms"), pochodzą ze spokojniejszego okna i są **rzędem
wielkości, nie pomiarem** — tak też je tam opisałem. Po czystym pomiarze
warto je zastąpić albo potwierdzić.

### Kryterium sukcesu

Dla każdego scenariusza podać medianę i odchylenie z >= 25 powtórzeń, przy
czym:

* **kontroler `admin: źródło (changelist)` musi wypaść stabilnie** (rozrzut
  < 10% mediany, brak flagi `SZUM`) — inaczej cały przebieg jest do
  wyrzucenia,
* różnicę uznajemy za realną tylko wtedy, gdy jest **większa niż rozrzut
  kontrolera**.

---

## Warunki wstępne na drugim komputerze

1. **Docker** (testcontainers + kontenery benchmarkowe).
2. **Cichy host** — żadnych równoległych suit testowych, `run-site` ani
   innych sesji agenta. To jest cały powód tego handoffu.
3. **Dump bazy produkcyjnej.** To jedyna rzecz, której NIE ma w repo:
   `db-backup-20260603-023000.tar.gz`, ~772 MB, leży na
   `/Volumes/SSD/` na `mac-mini` (symlink z `~`). Trzeba go przekopiować,
   np. przez udział SMB `mpasternak` albo `rsync`. Bez niego nie ma pomiaru
   — świeża baza nie pokaże N+1 (ma pojedyncze wiersze zamiast 504
   jednostek i 68 tys. autorów).
   Alternatywa: mniejszy `db-backup-20260428-093811.pg_dump` (~48 MB),
   ale ma inny wolumen danych, więc liczby nie będą porównywalne z tymi
   wyżej.

---

## Procedura

Cała mechanika jest opisana w `docs/deweloper/benchmark-orm.md` — poniżej
skrót właściwy dla tego zadania.

```bash
git clone git@github.com:iplweb/bpp.git && cd bpp
git checkout django-6.1
uv sync

# 1. Kontenery (nietypowe porty, żeby nie kolidować z niczym)
docker run -d --name bpp-bench-pg -p 55432:5432 \
  -e POSTGRES_USER=bpp -e POSTGRES_PASSWORD=password -e POSTGRES_DB=bpp \
  --shm-size=1g iplweb/bpp_dbserver:psql-16.13 \
  -c shared_buffers=1GB -c work_mem=64MB -c maintenance_work_mem=512MB
docker run -d --name bpp-bench-redis -p 55379:6379 redis:7-alpine

# 2. Baza (dump to format KATALOGOWY pg_dump -Fd w tarze, nie .sql!)
gzip -dc db-backup-20260603-023000.tar.gz | tar -xf -
PGPASSWORD=password pg_restore -h localhost -p 55432 -U bpp -d bpp \
  --no-owner --no-privileges --no-comments -j 6 db-backup-20260603-023000/
DJANGO_SETTINGS_MODULE=django_bpp.settings.bench \
  uv run python src/manage.py migrate --noinput

# 3. Pomiar PO zmianach (czubek django-6.1)
docker exec bpp-bench-redis redis-cli -n 7 FLUSHDB
DJANGO_SETTINGS_MODULE=django_bpp.settings.bench_prod \
  uv run python bench/bench_orm.py --pomiar --powtorzenia 25 > /tmp/po.txt

# 4. Pomiar PRZED zmianami — commit-rodzic squasha #733.
#    Harness trzeba przenieść, bo w ee5e81a35 jeszcze nie istniał:
git checkout ee5e81a35
git checkout django-6.1 -- bench/ src/django_bpp/settings/bench.py \
                           src/django_bpp/settings/bench_prod.py
docker exec bpp-bench-redis redis-cli -n 7 FLUSHDB
DJANGO_SETTINGS_MODULE=django_bpp.settings.bench_prod \
  uv run python bench/bench_orm.py --pomiar --powtorzenia 25 > /tmp/przed.txt
git checkout . && git checkout django-6.1
```

**UWAGA na `ee5e81a35`:** to stan przed CAŁĄ pracą wydajnościową na linii
6.1, czyli bez `FETCH_PEERS` — ale też bez poprawek z `dev` (A/C/D/B),
bo #733 wszedł jako squash i wciągnął je razem ze sobą. Czyli para
`ee5e81a35` vs `ccb9756ff` mierzy **efekt łączny wszystkich czterech
poprawek + FETCH_PEERS**, co jest dokładnie tym, co chcemy pokazać.

Jeśli chcesz rozbić wkład `FETCH_PEERS` osobno od poprawek A/C/D/B, użyj
`--tryb peers` na czubku `dev` (Django 5.2 nie ma fetch modes, więc to
trzeba zrobić na 6.1 — zob. „Ograniczenia" w dokumentacji harnessu).

### Czyszczenie po pomiarze

```bash
docker rm -f bpp-bench-pg bpp-bench-redis
```

---

## Pułapki, w które już wpadłem (nie powtarzaj)

1. **`grep -c` bez mianownika kłamie.** `grep -c "^\[ \]"` zwrócił `0`
   („brak zaległych migracji"), a komenda po prostu **wywaliła się
   tracebackiem** i nie wypisała nic. Zawsze licz też mianownik.
2. **`cmd > log 2>&1; echo "exit=$?"` w potoku mierzy exit ostatniego
   członu.** Dwa razy uwierzyłem w „exit 0", gdy `migrate` padał.
   Zapisuj kod wyjścia JAWNIE do pliku z logiem.
3. **`pytest ... | tail -25` gubi podsumowanie**, bo logi zamykanych
   kontenerów testcontainers wychodzą PO nim. Zapisuj pełny output do
   pliku i grepuj.
4. **Cacheops pikluje instancje modeli.** Pomiar 6.1 czytający wpisy
   zapisane przez 5.2 daje `RuntimeWarning` i nieważne wyniki. `FLUSHDB`
   przy każdej zmianie wersji.
5. **`constance` odrzuca LocMemCache** (`ImproperlyConfigured`) — dlatego
   `bench.py` trzyma `constance_cache` na Redisie.
6. **Nie wyrzucaj `easyaudit` z `INSTALLED_APPS`** — `bpp.0470` deklaruje
   zależność migracji od `easyaudit.0001_initial`, więc graf migracji się
   nie zbuduje. Wystarczy zgasić middleware i hooki sygnałów (tak robi
   `bench.py`).
7. **Nie ubijaj kontenerów wzorcem na współdzielonym hoście.** Przy
   sprzątaniu dwa razy trafiły mi na listę „sierot" CUDZE, żywe przebiegi
   pytest — bo w trakcie detekcji startował kolejny Ryuk. Selekcjonuj po
   nazwie/ID i wypisz listę PRZED usunięciem.

---

## Stan repozytorium

* `dev` — wypchnięte, `6416e2ac0`
* `django-6.1` — wypchnięte, `ccb9756ff` (+ ten handoff i `bench/`)
* PR #733 — **zmergowany**
* PR #731 (Django 6.1 → dev) — otwarty
* `AUDYT-DJANGO-6.1-WYDAJNOSC.md` — nietrackowany, tylko na `mac-mini`;
  jeśli potrzebny na drugiej maszynie, skopiuj razem z dumpem
