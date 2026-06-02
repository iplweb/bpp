# Single Celery worker + konfiguracja przez zmienne środowiskowe

Data: 2026-06-02
Branch/worktree: `worktree-single-worker` (`~/Programowanie/bpp-single-worker`)

## Problem

Dziś dwa osobne serwisy-konsumenci Celery nasłuchują na różnych kolejkach:

- `workerserver-general` — `celery worker -Q celery` (kolejka domyślna),
- `workerserver-denorm` — `celery worker -Q denorm` (kolejka denormalizacji).

To dwa procesy/kontenery tam, gdzie wystarczy jeden. Zadania z kolejki
`denorm` (`denorm.tasks.flush_single`) są krótkie i szybkie, więc spokojnie
współdzielą jeden worker z kolejką domyślną — nie potrzeba dedykowanego
serwera ani osobnego mechanizmu priorytetów.

Dodatkowo: worker nie ma dziś jawnej kontroli concurrency na produkcji —
Celery (pool prefork) bierze domyślnie `os.cpu_count()`, czyli tyle procesów
ile rdzeni hosta. To zbyt agresywne. Chcemy domyślnie **75% rdzeni** oraz
**pełną konfigurację workera przez zmienne środowiskowe** (pula, concurrency,
prefetch, recykling procesów pod kątem pamięci — por. problem rosnącej
pamięci z S1162).

## Zakres

- **W tym zakresie:** repo `bpp` — entrypoint workera, `celery_tasks.py`
  (konfiguracja przez env), deweloperski `docker-compose.yml`.
- **Poza zakresem (osobno):** repo `bpp-deploy` (`docker-compose.workers.yml`)
  — patrz sekcja „Następstwa w bpp-deploy". Tej zmiany NIE robimy teraz.
- Producent `denorm-queue` (`manage.py denorm_queue`, PostgreSQL `LISTEN` →
  kolejka `denorm`) i sama nazwa kolejki `denorm` — **bez zmian**. Zmieniamy
  wyłącznie stronę konsumenta (scalenie dwóch workerów w jeden).
- Mechanizm priorytetów Celery — **świadomie pomijamy** (zadania denorm są
  krótkie; round-robin Redisa po `-Q celery,denorm` w zupełności wystarcza).

## Decyzje projektowe

1. **Jeden worker konsumuje obie kolejki.** Domyślna wartość `CELERY_QUEUE`
   w entrypoincie zmienia się z `celery` na `celery,denorm`. Jeden worker bez
   nadpisania konsumuje obie kolejki. Brak ścisłego priorytetu — akceptowalne.

2. **Pełna konfiguracja workera przez env, scentralizowana w `app.conf`.**
   Konfiguracja siedzi w `src/django_bpp/celery_tasks.py` (czyta `os.environ`),
   nie w entrypoincie. Powód: `app.conf` jest honorowane niezależnie od sposobu
   startu (prod docker, dev `docker-compose`, `run-site`, ew. ręczny start),
   więc to jedno źródło prawdy. Flaga CLI `--concurrency` i tak ma pierwszeństwo
   nad configiem, więc bpp-deploy zachowuje furtkę „env albo flaga".

3. **75% rdzeni tylko dla puli prefork (prod/Linux).** macOS pozostaje przy
   `worker_pool=threads` + `worker_concurrency=10` (prefork + C-extensions
   segfaultuje po forku na Darwinie — istniejący warunek w `celery_tasks.py`).
   Na macOS 75% z wielordzeniowego Maca nie ma sensu dla deva.

4. **Caveat CPU w kontenerze.** `os.cpu_count()` zwraca liczbę rdzeni *hosta*
   i ignoruje cgroup CPU-quota (`--cpus`). To jednak dokładnie ta sama baza,
   której Celery używa dziś jako default, więc „75% z tego" jest wierne
   dotychczasowemu zachowaniu. Kto chce twardo przyciąć — ustawia jawne
   `CELERY_WORKER_CONCURRENCY`.

## Powierzchnia zmiennych środowiskowych

Wszystkie opcjonalne, z sensownymi domyślnymi wartościami:

| Zmienna | Default | Działanie |
|---|---|---|
| `CELERY_QUEUE` | `celery,denorm` | kolejki konsumowane przez worker (entrypoint, flaga `-Q`) |
| `CELERY_WORKER_POOL` | `prefork` (Linux), `threads` (macOS) | typ puli (`worker_pool`) |
| `CELERY_WORKER_CONCURRENCY` | *(puste)* | jawny int; jeśli ustawione — wygrywa nad procentem |
| `CELERY_WORKER_CONCURRENCY_PERCENT` | `75` | % z `os.cpu_count()`; używane gdy brak jawnego concurrency i pula = prefork |
| `CELERY_WORKER_PREFETCH_MULTIPLIER` | *(Celery default = 4)* | `worker_prefetch_multiplier` |
| `CELERY_WORKER_MAX_TASKS_PER_CHILD` | *(puste)* | `worker_max_tasks_per_child` — recykling procesu po N zadaniach |
| `CELERY_WORKER_MAX_MEMORY_PER_CHILD` | *(puste)* | `worker_max_memory_per_child` (KB RSS) — recykling po przekroczeniu pamięci |

### Logika wyznaczania concurrency (`celery_tasks.py`)

```
is_darwin = platform.system() == "Darwin"
use_prefork_on_darwin = os.environ.get("CELERY_USE_PREFORK") == "1"
default_pool = "threads" if (is_darwin and not use_prefork_on_darwin) else "prefork"
pool = os.environ.get("CELERY_WORKER_POOL", default_pool)

explicit = int(os.environ["CELERY_WORKER_CONCURRENCY"])   # jeśli ustawione
if explicit:
    concurrency = explicit
elif pool == "threads":
    concurrency = 10                       # dotychczasowy default deva
else:                                      # prefork
    pct = int(os.environ.get("CELERY_WORKER_CONCURRENCY_PERCENT", "75"))
    concurrency = max(1, math.floor((os.cpu_count() or 1) * pct / 100))
```

Pozostałe knoby (`prefetch_multiplier`, `max_tasks_per_child`,
`max_memory_per_child`) mapują się na odpowiednie klucze `app.conf` tylko gdy
env jest ustawiony (puste = default Celery / brak limitu).

Konfiguracja stosowana jest dla wszystkich procesów importujących
`celery_tasks` (w tym appserver) — to bezpieczne, bo to jedynie ustawienia
configu; aktywne tylko gdy proces faktycznie startuje workera.

## Pliki do zmiany (repo bpp)

1. **`src/django_bpp/celery_tasks.py`** — zastąpić dotychczasowy wąski warunek
   macOS-only pełną, env-sterowaną konfiguracją puli/concurrency/recyklingu
   (jak wyżej). Zachować istniejący warunek Darwin→threads jako *default*,
   nadpisywalny env-em.

2. **`docker/workerserver/entrypoint-workerserver.sh`** — zmiana domyślnej
   `CELERY_QUEUE` z `celery` na `celery,denorm`. Reszta (`watchmedo`, `-Q`)
   bez zmian. (Concurrency/pool NIE idą tu — są w `app.conf`.)

3. **`docker-compose.yml` (dev)**:
   - usunąć serwis `workerserver-denorm`,
   - `workerserver-general` zostaje jako jedyny worker (konsumuje obie kolejki
     przez nowy default entrypointu); rozważyć rename na `workerserver`
     (do decyzji w planie — rename pociąga aktualizację `depends_on`),
   - usunąć martwe `WEB_CONCURRENCY=4` z serwisów workera (Celery tego nie
     czyta — to konwencja gunicorna; mylące),
   - poprawić `depends_on`: `denorm-queue` i `workerserver-status` wskazują dziś
     na `workerserver-denorm` (znika) → przepiąć na pozostały worker.

## Następstwa w bpp-deploy (OSOBNO, nie w tym zadaniu)

Plik `~/Programowanie/bpp-deploy/docker-compose.workers.yml`:

- usunąć serwis `workerserver-denorm` (`CELERY_QUEUE: "denorm"`),
- `workerserver-general` — bez `CELERY_QUEUE` (weźmie nowy default
  `celery,denorm` z obrazu), opcjonalnie dodać nowe env (np.
  `CELERY_WORKER_CONCURRENCY_PERCENT`, `CELERY_WORKER_MAX_TASKS_PER_CHILD`),
- `denorm-queue.depends_on` i `workerserver-status.depends_on` — przepiąć
  z `workerserver-denorm` na `workerserver-general`,
- działa to dopiero po opublikowaniu obrazu `iplweb/bpp_workerserver` z nowym
  defaultem entrypointu (zmiana #2 powyżej).

## Plan testów / weryfikacja

- `ruff format` + `ruff check` na zmienionych plikach.
- Test jednostkowy logiki wyznaczania concurrency (czysta funkcja —
  wydzielić, by dało się testować bez startu workera): kombinacje env
  (jawny int / procent / pula threads / brak env).
- Sanity: `celery -A django_bpp.celery_tasks worker -Q celery,denorm` startuje
  i raportuje w `inspect ping` (dev przez `run-site` lub docker-compose up).
- `docker compose config` waliduje poprawiony `docker-compose.yml` (brak
  wiszących `depends_on`).

## Założenia / pytania otwarte

- Rename `workerserver-general` → `workerserver` w dev compose: kosmetyka,
  rozstrzygnąć w planie (czy warto ruszać nazwę).
- Brak strict-priority jest świadomą decyzją (zadania denorm krótkie).
