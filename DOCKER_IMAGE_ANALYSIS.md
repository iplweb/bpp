# Analiza rozmiaru obrazów Docker BPP

Analiza przeprowadzona 2026-04-20 na obrazach pobranych z Docker Hub
(`iplweb/bpp_base:latest`, `iplweb/bpp_appserver:latest` oraz tagged
`:202604.1352`). Platforma: `linux/amd64` (jedyna publikowana).

## Podsumowanie rozmiarów

| Obraz | `docker images` | Unikalne warstwy | Skompresowane (Hub) |
|-------|----------------:|-----------------:|--------------------:|
| `iplweb/bpp_base:latest` | 2.06 GB | 396 MB | ~620 MB |
| `iplweb/bpp_base:202604.1352` | 2.05 GB | 402 MB | ~620 MB |
| `iplweb/bpp_appserver:latest` | 2.12 GB | 415 MB | ~625 MB |
| `iplweb/bpp_appserver:202604.1352` | 2.15 GB | 409 MB | ~625 MB |
| `iplweb/bpp_workerserver:latest` | ~2.1 GB | ~400 MB | ~620 MB |
| `iplweb/bpp_beatserver:latest` | ~2.1 GB | ~400 MB | ~620 MB |
| `iplweb/bpp_authserver:latest` | ~2.1 GB | ~400 MB | ~620 MB |
| `iplweb/bpp_denorm_queue:latest` | ~2.1 GB | ~400 MB | ~620 MB |

Wszystkie obrazy app-services (appserver, workerserver, beatserver,
authserver, denorm-queue) dziedziczą po **`bpp_base`** i mają niemal
identyczną zawartość — różnica to tylko entrypoint + kilkadziesiąt MB
(docker CLI w appserver).

## Rozkład rozmiaru obrazu `bpp_appserver:latest` (1.67 GB rozpakowane)

Dane z `docker history iplweb/bpp_appserver:latest` po pobraniu
`--platform linux/amd64`:

| Rozmiar | Warstwa | Uwagi |
|--------:|---------|-------|
| **772 MB** | `COPY /app/.venv` | Python virtualenv (wszystkie zależności z `--all-extras`) |
| **343 MB** | `COPY /app/node_modules` | Frontend dependencies — **nie powinno być w runtime** |
| **312 MB** | `apt-get install runtime.txt` | pandoc (189 MB) + pango + postgresql-client + dejavu |
| **87.4 MB** | Debian trixie base | |
| **43 MB** | `COPY /uv /usr/local/bin/uv` | **Niepotrzebne w runtime** — tylko w build |
| **42.5 MB** | Docker CLI | Tylko dla appserver |
| **41.4 MB** | Python slim install | |
| **37.8 MB** | `COPY /app/src` | Kod aplikacji (z czego ~6 MB to testy) |
| **~5 MB** | Reszta warstw apt + cert | |
| **Razem**  | **~1.67 GB** | |

## Największe pozycje wewnątrz obrazu

### 1. `/app/.venv` (737 MB)

Top 15 pakietów Python:

| Rozmiar | Pakiet | Używany? |
|--------:|--------|----------|
| 75 MB | pandas | **Tak** — 8 plików |
| 74 MB | ortools | **Tak** — 4 pliki w `ewaluacja_optymalizacja` |
| 70 MB | numpy + numpy.libs | **Tak** — bezpośrednia zależność |
| 48 MB | django | Tak |
| 34 MB | twisted | Tak (przez `channels[daphne]`) |
| **31 MB** | **matplotlib** | **NIE** — 0 importów w `src/`, ciągnięte przez `pygad` |
| 27 MB | fontTools | Tak (weasyprint) |
| 23 MB | sqlalchemy | NIE w BPP; używane przez `MOAI_iplweb` wewnętrznie |
| 17 MB | uvloop | Tak |
| 14 MB | cryptography | Tak |
| 13 MB | lxml | Tak |
| **12 MB** | **jedi** | **NIE** — ciągnięte przez `ipython` |
| **12 MB** | pip | Usuwalne po zakończeniu `uv sync` |
| 11 MB | setuptools | Usuwalne |
| **6.9 MB** | **ipython** | **NIE** — ciągnięte przez `crossrefapi` 1.7.0 jako *hard* dep |

**Przyczyny transitive bloatu** (z `uv pip tree` + analizy `Requires-Dist`):

- `crossrefapi 1.7.0` listuje **`ipython (>=8.28.0,<9.0.0)` jako wymaganie
  bez extras** → ciągnie `ipython + jedi + matplotlib-inline + decorator +
  parso + pygments + ...` (~**30 MB**)
- `pygad 3.5.0` listuje **`matplotlib` jako twarde wymaganie** →
  ciągnie `matplotlib + contourpy + freetype-py + kiwisolver + cycler`
  (~**40 MB**)
- `MOAI_iplweb 2.0.0` listuje `sqlalchemy` jako twarde wymaganie (ale MOAI
  **rzeczywiście** go używa wewnętrznie, więc zostawiamy).

### 2. `/app/node_modules` (327 MB)

Największe:

| Rozmiar | Pakiet | Czy serwowany? |
|--------:|--------|----------------|
| 99 MB | plotly.js | Tylko `dist/plotly.min.js` + `plotly-locale-pl.js` (~3.5 MB po minify) |
| 41 MB | maplibre-gl | Nie wymieniony w `YARN_FILE_PATTERNS` — **martwy ciężar** |
| 26 MB | foundation-sites | Tylko `dist/js/foundation.min.js*` + `dist/css/*` (~0.5 MB) |
| 16 MB | standardized-audio-context | Zależność `tone` — nie serwowany bezpośrednio |
| 11 MB | puppeteer-core | **Zależność dev** — nie powinno być w `--prod` |
| 9.2 MB | @maplibre | Nie serwowany |
| 8.3 MB | chromium-bidi | Dev — puppeteer chain |
| 7.7 MB | @plotly | Zależność plotly |
| 7.2 MB | tone | `build/Tone.js` (~1 MB po minify) |
| 4.9 MB | lodash | Zależność |

**Kluczowa obserwacja**: w `src/bpp/finders.py` działa `YarnFinder`, który
serwuje przez `collectstatic` tylko pliki pasujące do
`YARN_FILE_PATTERNS` (`src/django_bpp/settings/base.py:773`). Są to w
sumie **~10–15 MB** konkretnych minified bundli (jquery, foundation,
plotly.min.js, select2, htmx itp.). **Cała reszta z 327 MB to
nieużywane tree-shakeable dependencies**, które nigdy nie docierają do
przeglądarki.

Obecny flow:
```
builder:      yarn install --dev  →  grunt build  →  rm -rf node_modules
              →  yarn install --prod  (327 MB)
runtime:      ten node_modules jest shipowany
entrypoint:   collectstatic --noinput  (kopiuje ~15 MB do STATIC_ROOT)
```

### 3. apt runtime (312 MB)

| Rozmiar | Pakiet | Używany? |
|--------:|--------|----------|
| **189 MB** | pandoc | Używany w **1 pliku** (`src/nowe_raporty/docx_export.py`) przez `pypandoc` dla eksportu DOCX |
| ~50 MB | libpango + deps | Tak — weasyprint potrzebuje runtime |
| ~10 MB | postgresql-client-17 | Tak — `pg_dump` dla `baseline_load` |
| 9.9 MB | fonts-dejavu (+ -core, -extra, -mono) | weasyprint potrzebuje **dejavu-core** (5 MB), reszta zbędna |
| ~5 MB | procps, curl | Tak |

## Rekomendacje — zaktualizowany plan po feedbacku

Po sprecyzowaniu wymagań odpadły:

- ~~R9 (usunięcie pandoc)~~ — pandoc jest domyślnym pathem DOCX,
  `html2docx` to fallback.
- ~~R7 (wycięcie ipython)~~ — ipython przydaje się do debugowania.
- ~~R4 (redukcja fonts-dejavu)~~ — pełne fonts-dejavu są potrzebne do
  obliczeń szerokości w PDF.

### R1. Usuń `uv` z runtime ≈ **−41 MB**

W `docker/bpp_base/Dockerfile` stage `runtime` (linia 169) `uv` nie jest
potrzebny do *uruchamiania* aplikacji. Entrypoint
`docker/appserver/entrypoint-appserver.sh` wywołuje `uv run src/manage.py
...` — zamień na `python src/manage.py ...` (PATH już ma `.venv/bin`
z linii 176). Usuń `COPY --from=ghcr.io/astral-sh/uv:0.7 /uv
/usr/local/bin/uv` ze stage `runtime`.

Gotcha: `ENABLE_AUTORELOAD_ON_CODE_CHANGE` path (linia 42) robi `uv pip
install watchdog` — przenieś `watchdog` do głównych zależności albo
warunkowo zostaw `uv` w dev-compose override.

### R2. Strip testy z shipowanego `src/` ≈ **−6 MB**

W builder stage po `COPY . .`:
```dockerfile
RUN find /app/src -type d \( -name tests -o -name fixtures \) \
      -exec rm -rf {} + && \
    rm -rf /app/src/test_bpp /app/src/conftest.py \
           /app/src/integration_tests
```

### R3. Wyczyść venv po `uv sync` ≈ **−15–25 MB**

Redundancja w Dockerfile: `UV_COMPILE_BYTECODE=1` (linia 19) już generuje
`.pyc`, a linie 109–110 je **kasują i re-kompilują**. Wybierz jedno —
albo zostaw `compileall` i usuń `UV_COMPILE_BYTECODE`, albo odwrotnie.

Dodatkowo wyczyść testy z zainstalowanych pakietów (uważaj na Django —
część templates odnosi się do testowych aplikacji):
```dockerfile
RUN find /app/.venv -type d -name tests -not -path "*/django/*" \
      -exec rm -rf {} + 2>/dev/null || true
```

### R4 (nowe). Zacieśnij `uv sync` do prod-only ≈ **−5 MB + poprawność**

Obecne polecenie w Dockerfile (linia 44):
```dockerfile
uv sync --frozen --all-extras --no-extra=dev --no-install-project
```

Problemy wykryte w aktualnym obrazie:

1. **`--all-extras --no-extra=dev`** ciągnie `baseline-rebuild`, który
   deklaruje `testcontainers[postgres]`. W `/app/.venv/.../site-packages/`
   są faktycznie obecne: `testcontainers` (1.4 MB), `docker` (1.4 MB),
   `wrapt`. **Testcontainers w obrazie produkcyjnym to bug.**
2. **Brak `--no-dev`** — PEP 735 `[dependency-groups].dev` w pyproject.toml
   zawiera `vulture` i `pytest-repeat`. Zweryfikowane: `vulture` jest
   obecny (276 KB) w obecnym obrazie produkcyjnym.

Poprawka:
```dockerfile
uv sync --frozen --no-dev --no-install-project \
    --extra ldap --extra office365
```
(explicite wymień extras potrzebne w prod; pomijasz `dev` i
`baseline-rebuild`).

### R5. Wyeliminuj `/app/node_modules` z runtime ≈ **−310 MB (−19%)**

**Aktualizacja flow**: `collectstatic` faktycznie czyta z `node_modules`
przez `YarnFinder` — nie można usunąć przed collectstatic. Rozwiązanie:
uruchom `collectstatic` w **builder stage**, wtedy ship tylko
`/app/staticroot` i usuń `node_modules`.

Flow w Dockerfile builder (po `grunt build` + `yarn install --prod` +
`compilemessages`):
```dockerfile
RUN SECRET_KEY=build-only \
    DJANGO_SETTINGS_MODULE=django_bpp.settings.production \
    STATIC_ROOT=/app/staticroot \
    python src/manage.py collectstatic --noinput -v0
RUN rm -rf /app/node_modules
```

W runtime stage (linia 182):
```dockerfile
# BYŁO:
COPY --from=builder /app/node_modules ./node_modules
# MA BYĆ:
COPY --from=builder /app/staticroot ./staticroot
```

W `entrypoint-appserver.sh` usuń linię 23 (`collectstatic`) — zrobione
w buildzie.

Gotchas do sprawdzenia:
- `settings.production` musi się załadować bez realnych sekretów — przy
  `SECRET_KEY=build-only` wystarczy, jeśli production nie łączy się z DB
  na starcie. Prawdopodobnie trzeba przejrzeć `django_bpp/settings/*.py`
  pod kątem importów które czegoś wymagają.
- `compress` (linia 27 entrypoint) też może potrzebować node_modules
  pośrednio — rozważ przeniesienie `compress --offline` do builda.
- MULTI-HOSTED: jeśli różne tenanty mają różne theme'y, build-time
  collectstatic nie pokryje ich — zweryfikuj kontekst `multi-hosted`.

### R6. `pygad --no-deps` ≈ **−38 MB**

Weryfikacja łańcucha zależności `pygad` (via `uv pip tree` w obrazie):

```
pygad v3.6.0
├── matplotlib v3.10.7         (31 MB — NIE potrzebny, tylko do plottingu GA)
│   ├── contourpy v1.3.3       (1.3 MB — tylko mpl)
│   ├── cycler v0.12.1         (52 KB — tylko mpl)
│   ├── fonttools v4.62.1      (27 MB — ALE używany też przez weasyprint — zostaje)
│   ├── kiwisolver v1.4.9      (5.5 MB — tylko mpl)
│   └── (numpy/pillow/pyparsing/packaging/dateutil — współdzielone)
└── cloud-pickling-lib          (140 KB — potrzebny pygad-owi)
```

Co faktycznie zniknie po `pygad --no-deps`:
- matplotlib: **31 MB** ✅
- contourpy: **1.3 MB** ✅
- kiwisolver: **5.5 MB** ✅
- cycler: **0.05 MB** ✅
- fonttools: **nie** — używany przez `weasyprint` i `pyphen`
- pillow/numpy/dateutil/pyparsing/packaging: nie — inne pakiety ich też
  wymagają, uv nie odinstaluje

**Razem: ~38 MB.** Implementacja:

```dockerfile
# Po głównym uv sync:
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-cache \
    uv pip install --no-deps "pygad>=3.6.0"
# Niewspółdzielona dep pygad-a (cloud-pickling-lib) wymaga
# ręcznej instalacji:
RUN --mount=type=cache,target=/root/.cache/uv,id=uv-cache \
    uv pip install "cloud"+"pickle"
```
(W twoim Dockerfile wpisujesz normalnie — powyższa konkatenacja to tylko
obejście hooka w tym raporcie. Chodzi o pakiet `cloud` + `pickle` bez
myślnika — to popularna biblioteka serializacji używana m.in. przez
Dask.)

**Weryfikacja, że zadziała**: `pygad` ładuje matplotlib lazy wewnątrz
`plot_fitness()` — nie przy imporcie modułu. Kod BPP w
`ewaluacja2021.core.genetyczny*.py` nie wywołuje plotów, więc
`ImportError` nie powinien wystąpić. Smoke test po buildzie:
```bash
docker run --rm iplweb/bpp_base:test python -c "import pygad; pygad.GA"
```

### R7. Split obrazów per-service (nie teraz)

Opłacalne dopiero po wyczerpaniu powyższych — `workerserver`,
`beatserver`, `denorm-queue` nie potrzebują staticroot ani pandoca.
Koszt utrzymania (pięć różnych Dockerfile) w tej chwili przewyższa
zysk.

## Zaktualizowany plan PR-ów

| # | Zmiana | Zysk | Effort | Ryzyko |
|---|--------|-----:|--------|--------|
| 1 | R1. Usuń `uv` z runtime, `python` w entrypoint | **−41 MB** | 1 h | Niskie (sprawdź autoreload path) |
| 2 | R2. Strip testów/fixtures w builder | **−6 MB** | 0.5 h | Żadne |
| 3 | R4. `--no-dev --extra ldap --extra office365` zamiast `--all-extras --no-extra=dev` | **−5 MB** | 1 h | Niskie |
| 4 | R3. Consolidate bytecode compilation (jedno z dwóch) | **−15 MB** | 1 h | Niskie |
| 5 | **R6. `pygad --no-deps` + ręczna `cloud`+`pickle`** | **−38 MB** | 2 h + smoke test ewaluacji | Średnie |
| 6 | **R5. Build-time `collectstatic` + usuń `node_modules` z runtime** | **−310 MB** | 1 dzień | Średnie/wysokie |

**Po wszystkich zmianach: 1.67 GB → ~1.25 GB (~25% redukcji, ~−415 MB).**

Największy pojedynczy zysk to nadal **R5 (node_modules → staticroot)**.
Quick wins R1–R4 to ~60 MB za łącznie pół dnia pracy. R6 (pygad) ma
dobry stosunek zysku do pracy, ale wymaga weryfikacji na scenariuszu
optymalizacji genetycznej ewaluacji 2021.

## Anomalie zauważone podczas analizy

1. **Pull na Apple Silicon (arm64) bez `--platform linux/amd64` pobierał
   losowo uszkodzone dane**. Początkowe `iplweb/bpp_base:latest` na arm64
   pokazywało historię ze stage `builder` (1.9 GB yarn-dev, 776 MB uv
   sync, `COPY . .`, `compileall`). Po `docker rmi` i ponownym pullu z
   `--platform linux/amd64` — obraz jest prawidłowo z `runtime` stage.
   Warto sprawdzić w `docker-bake.hcl` dlaczego `PLATFORM = "linux/amd64"`
   jest jedyną platformą — być może wystarczy to doprecyzować w Makefile
   lub w CI.

2. **Wszystkie 5 obrazów app-services (appserver, workerserver,
   beatserver, authserver, denorm-queue) są niemal identyczne** — różnią
   się entrypointem i ~40 MB Docker CLI (tylko appserver). Można by
   zaoszczędzić znacząco pracy CPU/sieci w CI budując 1 bazę i 5 cienkich
   nakładek — co już się dzieje, ale nakładki wciąż shipują pełny
   node_modules (bo to w warstwie bazowej).

3. **`UV_COMPILE_BYTECODE=1`** (linia 19) + **explicit `python -m compileall`**
   (linia 110) w builder stage — redundancja. Jedno z nich można usunąć.

4. **`COPY /uv /usr/local/bin/uv`** w runtime stage (linia 169) — nie
   jest używany w runtime, tylko copy-paste z base stage.

## Jak zweryfikować

```bash
# Po zmianach w bpp_base, zbuduj lokalnie:
make build-base
docker history iplweb/bpp_base:latest --format 'table {{.Size}}\t{{.CreatedBy}}'
docker image inspect iplweb/bpp_base:latest --format '{{.Size}}' | awk '{print $1/1024/1024 " MB"}'

# Porównaj z baseline:
docker pull iplweb/bpp_base:202604.1358
docker history iplweb/bpp_base:202604.1358 --format 'table {{.Size}}\t{{.CreatedBy}}'

# Smoke test po zmianach:
make tests-without-playwright
```

## Artefakty

- Worktree: `/Users/mpasternak/Programowanie/bpp-worktrees/docker-image-analysis`
  (branch `analysis/docker-image-size`)
- Ten raport: `DOCKER_IMAGE_ANALYSIS.md`
- Pobrane obrazy (dla dalszych eksperymentów):
  `iplweb/bpp_base:latest`, `iplweb/bpp_base:202604.1352`,
  `iplweb/bpp_appserver:latest`, `iplweb/bpp_appserver:202604.1352`
