# Single Celery worker + konfiguracja przez env — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Scalić dwa serwisy-konsumenci Celery (general + denorm) w jeden worker nasłuchujący na `celery,denorm` i wprowadzić pełną konfigurację workera (pula, concurrency=75% rdzeni dla prefork, prefetch, recykling procesów) przez zmienne środowiskowe.

**Architecture:** Cała konfiguracja workera wyznaczana jest przez czystą funkcję `resolve_worker_config(environ, system, cpu_count)` w `src/django_bpp/celery_tasks.py`, której wynik trafia do `app.conf.update(...)` przy imporcie. Entrypoint workera zmienia tylko domyślną `CELERY_QUEUE` na `celery,denorm`. Dev `docker-compose.yml` traci serwis `workerserver-denorm`.

**Tech Stack:** Python 3.10+, Celery (broker Redis), Django, pytest, Docker Compose. Uruchamianie Pythona ZAWSZE przez `uv run`.

**Worktree:** `~/Programowanie/bpp-single-worker` (branch `worktree-single-worker`). Wszystkie komendy odpalać z tego katalogu.

**Spec:** `docs/superpowers/specs/2026-06-02-single-worker-design.md`

---

### Task 1: Czysta funkcja `resolve_worker_config` + testy

Wydzielamy logikę wyznaczania konfiguracji workera do funkcji czystej (bez side-effectów, bez czytania globalnego `os.environ`/`platform` w środku — wszystko przez argumenty), żeby dało się ją przetestować bez startu workera i bez mutowania środowiska.

**Files:**
- Modify: `src/django_bpp/celery_tasks.py`
- Test: `src/django_bpp/tests/test_celery_worker_config.py` (create)

- [ ] **Step 1: Write the failing test**

Utwórz `src/django_bpp/tests/test_celery_worker_config.py`:

```python
from django_bpp.celery_tasks import resolve_worker_config


def test_linux_prefork_defaults_to_75_percent_of_cores():
    cfg = resolve_worker_config(environ={}, system="Linux", cpu_count=8)
    assert cfg["worker_pool"] == "prefork"
    assert cfg["worker_concurrency"] == 6  # round(8 * 0.75)
    # opcjonalne knoby nieustawione -> nieobecne w configu
    assert "worker_max_tasks_per_child" not in cfg
    assert "worker_max_memory_per_child" not in cfg
    assert "worker_prefetch_multiplier" not in cfg


def test_macos_defaults_to_threads_pool_concurrency_10():
    cfg = resolve_worker_config(environ={}, system="Darwin", cpu_count=10)
    assert cfg["worker_pool"] == "threads"
    assert cfg["worker_concurrency"] == 10


def test_macos_prefork_override_uses_percent():
    cfg = resolve_worker_config(
        environ={"CELERY_USE_PREFORK": "1"}, system="Darwin", cpu_count=8
    )
    assert cfg["worker_pool"] == "prefork"
    assert cfg["worker_concurrency"] == 6


def test_explicit_concurrency_wins_over_percent():
    cfg = resolve_worker_config(
        environ={"CELERY_WORKER_CONCURRENCY": "3"}, system="Linux", cpu_count=8
    )
    assert cfg["worker_concurrency"] == 3


def test_concurrency_percent_env_overrides_default_75():
    cfg = resolve_worker_config(
        environ={"CELERY_WORKER_CONCURRENCY_PERCENT": "50"},
        system="Linux",
        cpu_count=8,
    )
    assert cfg["worker_concurrency"] == 4  # round(8 * 0.50)


def test_concurrency_never_below_one():
    cfg = resolve_worker_config(
        environ={"CELERY_WORKER_CONCURRENCY_PERCENT": "10"},
        system="Linux",
        cpu_count=1,
    )
    assert cfg["worker_concurrency"] == 1  # max(1, round(0.1)) -> 1


def test_explicit_pool_override():
    cfg = resolve_worker_config(
        environ={"CELERY_WORKER_POOL": "gevent"}, system="Linux", cpu_count=8
    )
    assert cfg["worker_pool"] == "gevent"
    # pula != threads i != prefork-z-procentem: nieprefork traktujemy
    # jak "potrzebuje concurrency" -> procent z rdzeni
    assert cfg["worker_concurrency"] == 6


def test_optional_memory_and_prefetch_knobs_passed_through():
    cfg = resolve_worker_config(
        environ={
            "CELERY_WORKER_PREFETCH_MULTIPLIER": "1",
            "CELERY_WORKER_MAX_TASKS_PER_CHILD": "100",
            "CELERY_WORKER_MAX_MEMORY_PER_CHILD": "500000",
        },
        system="Linux",
        cpu_count=4,
    )
    assert cfg["worker_prefetch_multiplier"] == 1
    assert cfg["worker_max_tasks_per_child"] == 100
    assert cfg["worker_max_memory_per_child"] == 500000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd ~/Programowanie/bpp-single-worker && uv run pytest src/django_bpp/tests/test_celery_worker_config.py -p no:cacheprovider -v`
Expected: FAIL z `ImportError: cannot import name 'resolve_worker_config'`.

- [ ] **Step 3: Write minimal implementation**

W `src/django_bpp/celery_tasks.py` dodaj funkcję (powyżej bloku, który dotąd robił warunek Darwin). Pełna treść funkcji:

```python
def resolve_worker_config(environ, system, cpu_count):
    """Wyznacz konfigurację workera Celery na podstawie zmiennych środowiskowych.

    Czysta funkcja (bez side-effectów) — wszystkie wejścia przez argumenty,
    żeby dało się ją testować bez startu workera i bez mutowania os.environ.

    Zwraca dict gotowy do `app.conf.update(...)`. Opcjonalne knoby (prefetch,
    max_tasks/max_memory_per_child) trafiają do wyniku tylko gdy env ustawiony.
    """
    use_prefork_on_darwin = environ.get("CELERY_USE_PREFORK") == "1"
    is_darwin = system == "Darwin"
    default_pool = "threads" if (is_darwin and not use_prefork_on_darwin) else "prefork"
    pool = environ.get("CELERY_WORKER_POOL", default_pool)

    explicit = environ.get("CELERY_WORKER_CONCURRENCY")
    if explicit:
        concurrency = int(explicit)
    elif pool == "threads":
        # Dotychczasowy default deva (macOS): prefork + C-ext segfaultuje po forku.
        concurrency = 10
    else:
        percent = int(environ.get("CELERY_WORKER_CONCURRENCY_PERCENT", "75"))
        concurrency = max(1, round((cpu_count or 1) * percent / 100))

    config = {"worker_pool": pool, "worker_concurrency": concurrency}

    # Opcjonalne knoby — tylko gdy jawnie ustawione (puste = default Celery).
    optional = {
        "CELERY_WORKER_PREFETCH_MULTIPLIER": "worker_prefetch_multiplier",
        "CELERY_WORKER_MAX_TASKS_PER_CHILD": "worker_max_tasks_per_child",
        "CELERY_WORKER_MAX_MEMORY_PER_CHILD": "worker_max_memory_per_child",
    }
    for env_name, conf_key in optional.items():
        value = environ.get(env_name)
        if value:
            config[conf_key] = int(value)

    return config
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd ~/Programowanie/bpp-single-worker && uv run pytest src/django_bpp/tests/test_celery_worker_config.py -p no:cacheprovider -v`
Expected: PASS (8 passed).

- [ ] **Step 5: Commit**

```bash
cd ~/Programowanie/bpp-single-worker
git add src/django_bpp/celery_tasks.py src/django_bpp/tests/test_celery_worker_config.py
git commit -m "feat(celery): czysta funkcja resolve_worker_config + testy"
```

---

### Task 2: Podpięcie `resolve_worker_config` do `app.conf` przy imporcie

Zastępujemy dotychczasowy wąski warunek macOS-only wywołaniem funkcji z Tasku 1 dla WSZYSTKICH platform.

**Files:**
- Modify: `src/django_bpp/celery_tasks.py:11-22`

- [ ] **Step 1: Zamień blok konfiguracji**

Obecny kod (`src/django_bpp/celery_tasks.py`, linie ~11-22):

```python
if platform.system() == "Darwin":
    os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")

app = Celery("django_bpp")
app.config_from_object("django.conf:settings")
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
app.autodiscover_tasks(lambda: [n.name for n in apps.get_app_configs()])

# On macOS, prefork + C extensions (psycopg2, numpy, lxml, etc.) can segfault after fork.
# Default to threads locally unless explicitly overridden.
if platform.system() == "Darwin" and os.environ.get("CELERY_USE_PREFORK") != "1":
    app.conf.update(worker_pool="threads", worker_concurrency=10)
```

Zastąp blokiem (funkcja `resolve_worker_config` została dodana w Tasku 1, tu zostawiamy ją powyżej `app = Celery(...)` — kolejność: import os/platform, definicja funkcji, potem poniższe):

```python
if platform.system() == "Darwin":
    os.environ.setdefault("OBJC_DISABLE_INITIALIZE_FORK_SAFETY", "YES")

app = Celery("django_bpp")
app.config_from_object("django.conf:settings")
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)
app.autodiscover_tasks(lambda: [n.name for n in apps.get_app_configs()])

# Konfiguracja workera (pula, concurrency=75% rdzeni dla prefork, prefetch,
# recykling procesów) — w pełni sterowalna przez zmienne środowiskowe.
# Patrz docs/superpowers/specs/2026-06-02-single-worker-design.md.
# macOS domyślnie threads (prefork + C-ext segfaultuje po forku).
app.conf.update(
    resolve_worker_config(
        environ=os.environ,
        system=platform.system(),
        cpu_count=os.cpu_count(),
    )
)
```

- [ ] **Step 2: Sanity — import się ładuje, nic nie wybucha**

Run: `cd ~/Programowanie/bpp-single-worker && uv run python -c "from django_bpp.celery_tasks import app; print(app.conf.worker_pool, app.conf.worker_concurrency)"`
Expected: wypisze `threads 10` na macOS (dev) — bez błędu importu.

- [ ] **Step 3: Re-run testów z Tasku 1 (regresja)**

Run: `cd ~/Programowanie/bpp-single-worker && uv run pytest src/django_bpp/tests/test_celery_worker_config.py -p no:cacheprovider -v`
Expected: PASS (8 passed).

- [ ] **Step 4: Commit**

```bash
cd ~/Programowanie/bpp-single-worker
git add src/django_bpp/celery_tasks.py
git commit -m "feat(celery): konfiguracja workera przez env dla wszystkich platform"
```

---

### Task 3: Entrypoint — domyślna `CELERY_QUEUE=celery,denorm`

Jeden worker konsumuje obie kolejki, gdy nikt nie nadpisze `CELERY_QUEUE`.

**Files:**
- Modify: `docker/workerserver/entrypoint-workerserver.sh:5`

- [ ] **Step 1: Zmień default**

Obecna linia 5:

```sh
CELERY_QUEUE=${CELERY_QUEUE:-celery}
```

Zmień na:

```sh
CELERY_QUEUE=${CELERY_QUEUE:-celery,denorm}
```

(Reszta pliku — `watchmedo` / `-Q $CELERY_QUEUE` — bez zmian. Pool/concurrency NIE idą tu; są w `app.conf`.)

- [ ] **Step 2: Sanity — skrypt parsuje się poprawnie**

Run: `cd ~/Programowanie/bpp-single-worker && sh -n docker/workerserver/entrypoint-workerserver.sh && echo OK`
Expected: `OK` (brak błędów składni).

- [ ] **Step 3: Commit**

```bash
cd ~/Programowanie/bpp-single-worker
git add docker/workerserver/entrypoint-workerserver.sh
git commit -m "feat(docker): worker domyslnie konsumuje kolejki celery,denorm"
```

---

### Task 4: Dev `docker-compose.yml` — jeden worker, naprawa zależności

Usuwamy `workerserver-denorm`, usuwamy martwe `WEB_CONCURRENCY=4`, przepinamy `depends_on`. Nazwę `workerserver-general` ZACHOWUJEMY (rename poza zakresem — minimalizujemy diff i ryzyko rozjazdu z bpp-deploy, gdzie serwis też nazywa się `workerserver-general`).

**Files:**
- Modify: `docker-compose.yml`

- [ ] **Step 1: Usuń serwis `workerserver-denorm`**

Usuń cały blok serwisu `workerserver-denorm` (w obecnym pliku linie ~159-189, od `  workerserver-denorm:` do końca jego `depends_on`, tuż przed `  workerserver-status:`).

- [ ] **Step 2: Usuń martwe `WEB_CONCURRENCY=4` z `workerserver-general`**

W serwisie `workerserver-general` (sekcja `environment:`) usuń linię:

```yaml
      - WEB_CONCURRENCY=4
```

(Celery tego nie czyta — to konwencja gunicorna; zostawienie wprowadza w błąd.)

- [ ] **Step 3: Przepnij `depends_on` w `workerserver-status`**

Obecnie `workerserver-status.depends_on` zawiera:

```yaml
    depends_on:
      workerserver-general:
        condition: service_healthy
      workerserver-denorm:
        condition: service_healthy
```

Zmień na (usuń wpis o nieistniejącym `workerserver-denorm`):

```yaml
    depends_on:
      workerserver-general:
        condition: service_healthy
```

- [ ] **Step 4: Przepnij `depends_on` w `denorm-queue`**

Obecnie `denorm-queue.depends_on`:

```yaml
    depends_on:
      redis:
        condition: service_healthy
      workerserver-denorm:
        condition: service_healthy
```

Zmień na:

```yaml
    depends_on:
      redis:
        condition: service_healthy
      workerserver-general:
        condition: service_healthy
```

- [ ] **Step 5: Zaktualizuj komentarz nagłówkowy sekcji Application**

W komentarzu (obecnie linia ~59):

```yaml
  # Wszystkie serwisy aplikacyjne (appserver/celerybeat/workerserver*/denorm-queue)
```

`workerserver*` nadal pasuje (jest `workerserver-general` i `workerserver-status`), więc komentarz zostaje bez zmian — ten krok to tylko weryfikacja, że nie ma osieroconych odniesień do `workerserver-denorm` w komentarzach.

Run: `cd ~/Programowanie/bpp-single-worker && grep -n "workerserver-denorm" docker-compose.yml || echo "CLEAN"`
Expected: `CLEAN` (żadnych pozostałości).

- [ ] **Step 6: Walidacja compose**

Run: `cd ~/Programowanie/bpp-single-worker && docker compose config >/dev/null && echo "COMPOSE OK"`
Expected: `COMPOSE OK` (brak wiszących `depends_on`, plik poprawny). Jeśli Docker niedostępny w środowisku — pominąć i odnotować.

- [ ] **Step 7: Commit**

```bash
cd ~/Programowanie/bpp-single-worker
git add docker-compose.yml
git commit -m "feat(docker): dev compose - jeden worker konsumuje celery,denorm"
```

---

### Task 5: Weryfikacja końcowa (ruff + pełny import + sanity workera)

**Files:** (brak nowych — tylko weryfikacja)

- [ ] **Step 1: ruff format + check na zmienionych plikach Pythona**

Run:
```bash
cd ~/Programowanie/bpp-single-worker
uv run ruff format src/django_bpp/celery_tasks.py src/django_bpp/tests/test_celery_worker_config.py
uv run ruff check src/django_bpp/celery_tasks.py src/django_bpp/tests/test_celery_worker_config.py
```
Expected: brak błędów; jeśli format coś zmienił — dołączyć do commita w Step 4.

- [ ] **Step 2: Pełny test config workera**

Run: `cd ~/Programowanie/bpp-single-worker && uv run pytest src/django_bpp/tests/test_celery_worker_config.py -p no:cacheprovider -v`
Expected: PASS (8 passed).

- [ ] **Step 3: Sanity workera — startuje i konsumuje obie kolejki**

Run (wymaga działającego dev stacka; opcjonalny — jeśli `run-site` nie biegnie, pominąć i odnotować):
```bash
cd ~/Programowanie/bpp-single-worker
uv run celery -A django_bpp.celery_tasks worker -Q celery,denorm --loglevel=info &
sleep 8
uv run celery -A django_bpp.celery_tasks inspect active_queues 2>/dev/null | grep -E "celery|denorm"
kill %1
```
Expected: w `active_queues` widoczne `celery` ORAZ `denorm`.

- [ ] **Step 4: Commit ewentualnych poprawek formatowania**

```bash
cd ~/Programowanie/bpp-single-worker
git add -A
git diff --cached --quiet || git commit -m "style: ruff format po zmianach worker config"
```

---

## Notatka: następstwa w bpp-deploy (OSOBNE zadanie, NIE w tym planie)

Po opublikowaniu obrazu `iplweb/bpp_workerserver` z nowym defaultem entrypointu, w `~/Programowanie/bpp-deploy/docker-compose.workers.yml`:

- usunąć serwis `workerserver-denorm` (`CELERY_QUEUE: "denorm"`),
- `workerserver-general` — zostawić bez `CELERY_QUEUE` (weźmie default `celery,denorm`); opcjonalnie dodać `CELERY_WORKER_CONCURRENCY_PERCENT`, `CELERY_WORKER_MAX_TASKS_PER_CHILD`, `CELERY_WORKER_MAX_MEMORY_PER_CHILD`,
- przepiąć `depends_on` w `denorm-queue` i `workerserver-status` z `workerserver-denorm` na `workerserver-general`.
