<p align="center">
  <img src="https://github.com/iplweb/bpp/raw/dev/src/bpp/static/bpp/images/logo_bpp.png" width="480" alt="Logo BPP">
</p>

<h1 align="center">BPP — Bibliografia Publikacji Pracowników</h1>

<p align="center">
  <a href="https://github.com/iplweb/bpp/actions/workflows/tests.yml"><img src="https://github.com/iplweb/bpp/actions/workflows/tests.yml/badge.svg?branch=dev" alt="Testy"></a>
  <a href="https://github.com/iplweb/bpp/actions/workflows/build-docker-images.yml"><img src="https://github.com/iplweb/bpp/actions/workflows/build-docker-images.yml/badge.svg?branch=master" alt="Docker - oficjalne obrazy"></a>
  <a href="https://iplweb.github.io/bpp/"><img src="https://github.com/iplweb/bpp/actions/workflows/docs.yml/badge.svg?branch=dev" alt="Dokumentacja"></a>
</p>

<p align="center">
  <b>Wsparcie komercyjne zapewnia</b><br><br>
  <a href="https://bpp.iplweb.pl"><img src="https://www.iplweb.pl/images/ipl-logo-large.png" width="150" alt="IPL Web"></a>
</p>

## O projekcie

Bibliografia Publikacji Pracowników to system informatyczny do zarządzania
bibliografią publikacji pracowników naukowych. Oprogramowanie przeznaczone
jest dla bibliotek naukowych i uniwersyteckich w Polsce.

Oprogramowanie dystrybuowane jest na zasadach otwartoźródłowej
[licencji MIT](https://pl.wikipedia.org/wiki/Licencja_MIT).

## Główne funkcje

- Zarządzanie bibliografią publikacji pracowników naukowych
- Centralny punkt przyjmowania i obróbki publikacji na uczelni
- Integracja z Polską Bibliografią Naukową (PBN)
- Integracja z ORCID i CrossRef
- Integracja z Web of Science
- Dwukierunkowa integracja z repozytoriami DSpace (import oraz wysyłanie prac)
- Wystawianie danych przez OAI-PMH oraz API
- Raporty ewaluacyjne i analiza slotów
- Ranking autorów i punktacja publikacji
- Klasyfikacja i śledzenie Open Access
- Import i eksport danych z zewnętrznych systemów
- System zgłaszania publikacji przez pracowników
- Powiadomienia w czasie rzeczywistym

## Integracje — BPP jako centralny hub danych

BPP pełni rolę **centralnego punktu przyjmowania i obróbki publikacji**
na uczelni. Dane wpływają do systemu z wielu źródeł, są w nim
ujednolicane, weryfikowane i punktowane, a następnie udostępniane dalej
przez zestaw kanałów wyjściowych.

<p align="center">
  <img src="https://github.com/iplweb/bpp/raw/dev/src/bpp/static/bpp/images/bpp_integracje.svg" width="900" alt="Schemat architektury wymiany danych BPP — po lewej wejścia (Pracownicy, PBN, CrossRef, Web of Science, DSpace), w centrum BPP jako hub, po prawej wyjścia (PBN, OAI-PMH, API, DSpace)">
</p>

- **Wejście (input)** — dane trafiają do BPP od **pracowników**
  (zgłaszanie publikacji), z **PBN**, **CrossRef**, **Web of Science**
  oraz z repozytoriów **DSpace** (import publikacji wraz z metadanymi
  Dublin Core, autodetekcja DSpace 6/7).
- **Wyjście (output)** — z BPP dane wypływają do **PBN**, są wystawiane
  przez **OAI-PMH** (zbiór do agregatorów i discovery), udostępniane
  programistycznie przez **API**, a prace mogą być **wysyłane do
  repozytorium DSpace**, dzięki czemu BPP staje się jednym, spójnym
  miejscem zasilania całego ekosystemu publikacyjnego uczelni.

### Integracja z DSpace (dwukierunkowa)

BPP integruje się z repozytoriami instytucjonalnymi opartymi o **DSpace**
w obie strony:

- **DSpace → BPP** — import publikacji z repozytorium na podstawie adresu
  rekordu (`/items/{uuid}` dla DSpace 7+ oraz `/handle/{prefix}/{suffix}`
  dla DSpace 6). BPP odczytuje metadane (tytuł, autorzy, rok, DOI,
  ISSN/ISBN, typ, abstrakt, słowa kluczowe, licencja) i zakłada na ich
  podstawie rekord.
- **BPP → DSpace** — wysyłanie prac z BPP do repozytorium DSpace, tak aby
  BPP było centralnym punktem rejestracji i obróbki, a repozytorium
  otrzymywało gotowe, opisane rekordy.

## Wymagania systemowe

- PostgreSQL
- Redis
- Docker (zalecany sposób wdrożenia)

## Instalacja

> **Wdrożenie produkcyjne BPP odbywa się przez repozytorium
> [bpp-deploy](https://github.com/iplweb/bpp-deploy).** Tam znajdziesz
> kompletny zestaw plików `docker compose`, konfiguracji nginx i skryptów
> uruchomieniowych przygotowanych pod realny serwer.

Dwa podstawowe źródła informacji o instalacji:

- **[github.com/iplweb/bpp-deploy](https://github.com/iplweb/bpp-deploy)** —
  gotowe pliki deploymentu (Docker Compose, nginx, named volumes,
  upgrade workflow).
- **[bpp.iplweb.pl/zrodla](https://bpp.iplweb.pl/zrodla)** — opis
  procesu wdrożeniowego krok po kroku.

Oficjalne obrazy Dockera publikowane są pod `iplweb/bpp_appserver`
i `iplweb/bpp_dbserver` (status buildu — zobacz badge „Docker" na
górze strony).

Jeśli zamiast wdrożenia chcesz **rozwijać kod BPP lokalnie**, przejdź
do sekcji [Praca nad kodem (Linux)](#praca-nad-kodem-linux) poniżej.

## Wersja demo

Live-demo serwisu dostępne jest na żądanie — prosimy o kontakt
pod adresem e-mail michal.dtz@gmail.com.

## Praca nad kodem (Linux)

> **To NIE jest instrukcja wdrożenia produkcyjnego.** Jeżeli chcesz
> zainstalować BPP na serwerze, skorzystaj z repozytorium
> **[bpp-deploy](https://github.com/iplweb/bpp-deploy)**. Poniższe kroki
> opisują wyłącznie konfigurację lokalnego środowiska deweloperskiego
> i uruchamianie testów.
>
> **Pierwsze wykonanie poniższych kroków może trwać bardzo długo** —
> ściągane są zależności Pythona, paczki npm/yarn, przeglądarki Playwright
> oraz obrazy Dockera dla testcontainers (PostgreSQL, Redis).
> Łącznie kilkaset MB do kilku GB transferu sieciowego. Pod każdym krokiem
> podany jest sposób, jak włączyć szczegółowe logowanie postępu.

### Skrót — szybki start (TL;DR)

Od zera do zielonych testów (macOS / Linux):

```bash
git clone https://github.com/iplweb/bpp.git && cd bpp
make prepare-developer-machine    # systemowe libki + uv sync + playwright
make assets                       # yarn install + grunt build + compilemessages
uv run pytest -n auto             # testy równolegle (pytest-xdist)
```

Wymagania: **Docker daemon** (do testcontainers), Homebrew (macOS) lub
`apt` + `sudo` (Linux). Pierwszy bieg pobiera kilkaset MB do paru GB
(pakiety npm, przeglądarki Playwright, obrazy Dockera dla testów).

Co robi `make prepare-developer-machine`:

- **macOS** (Apple Silicon, Homebrew) — przez `brew`: `cairo`, `pango`,
  `gdk-pixbuf`, `libffi`, `gobject-introspection`, `gtk+3`, `node`,
  `yarn`; przez `npm` globalnie `grunt-cli`; tworzy `sudo`-symlinki
  w `/usr/local/lib` na libki z `/opt/homebrew/lib`
  (`dyld` nie konsultuje brew-owej ścieżki domyślnie, a `DYLD_FALLBACK_LIBRARY_PATH`
  jest stripowana przez SIP w podprocesach — patrz
  [docs/MACOS_WEASYPRINT.md](docs/MACOS_WEASYPRINT.md)); na końcu
  `uv sync --frozen --no-install-project --all-extras` +
  `uv run playwright install`.
- **Linux** (Debian/Ubuntu, `apt`) — przez `sudo apt`: `yarnpkg`,
  `nodejs`, `npm`, `python3-dev`, `libpq-dev`, `libcairo2-dev`,
  `libpango1.0-dev`, `libgdk-pixbuf2.0-dev`, `libffi-dev`,
  `libgirepository1.0-dev`, `libgtk-3-dev`; przez `sudo npm` globalnie
  `grunt-cli`; na końcu `uv sync --frozen --no-install-project
  --all-extras` + `uv run playwright install --with-deps` (z systemowymi
  libkami chromium — wymaga sudo).

Auto-detekcja systemu jest domyślna; aby wymusić wariant:
`make prepare-developer-machine-macos` albo
`make prepare-developer-machine-linux`. Cel **nie woła `make assets`** —
frontend trzeba zbudować osobno.

`pytest -n auto` (`pytest-xdist`) rozdziela testy między workery; każdy
worker dostaje **własny** testcontainer PostgreSQL/Redis na losowym
porcie, więc nie ma kolizji. Kolejne biegi z `PYTEST_TESTCONTAINERS_REUSE=1`
są znacznie szybsze (kontenery nie znikają między uruchomieniami).

Jeżeli przeglądarki Playwright trzeba zainstalować osobno (np. po
samodzielnym `uv sync`), bez resetowania reszty środowiska:

```bash
make playwright-install
```

Poniżej szczegółowy opis krok po kroku — gdy chcesz wiedzieć, co
dokładnie robi każdy etap albo musisz wykonać tylko fragment.

### 1. Sklonuj repozytorium

```bash
git clone https://github.com/iplweb/bpp.git
cd bpp
```

### 2. Zainstaluj zależności Pythona i Playwright

```bash
uv sync
uv run playwright install
sudo playwright install-deps
```

`uv sync` instaluje pakiety potrzebne do pracy i testów (pytest,
pytest-django, model-bakery, ruff, pre-commit, …) — siedzą one w
`[dependency-groups].dev`, którą `uv` aktywuje defaultowo (opt-out
przez `--no-dev`). `uv run playwright install` pobiera przeglądarki
używane w testach E2E (~500 MB). `sudo playwright install-deps`
doinstalowuje systemowe biblioteki, których wymagają te przeglądarki
(libnss3, libatk, libgtk-3, …) — wymaga sudo, bo używa `apt`.

Aby uzyskać dodatkowe logowanie postępu:

- `uv sync -v` — verbose output uv
- `uv run playwright install --with-deps` — alternatywa, która sama
  wywołuje `apt` (jeśli wolisz nie rozdzielać kroku z sudo)

### 3. Zbuduj assety frontendowe

```bash
make assets
```

Ten krok uruchamia `yarn install` (pierwszy raz pobiera kilkaset MB
zależności Node.js do `node_modules/`), następnie `grunt build`
(kompilacja SCSS → CSS, bundling JS) oraz `compilemessages` (tłumaczenia
Django). Pierwsze wykonanie trwa kilka minut.

Aby zobaczyć szczegółowy postęp:

```bash
yarn install --verbose      # zanim uruchomisz make assets
grunt build --verbose       # alternatywa dla `make grunt-build`
```

### 4. Uruchom testy

```bash
uv run pytest
```

Pytest startuje **własne** kontenery Docker (PostgreSQL, Redis)
przez plugin `pytest-testcontainers-django` — przy pierwszym
uruchomieniu pobiera obrazy z Docker Hub (kolejne kilkaset MB).
Wymagany jest działający **Docker daemon**.

Pełen suite może trwać do **10 minut**. Domyślnie `pytest-sugar` pokazuje
pasek postępu, ale jeśli chcesz więcej szczegółów:

```bash
uv run pytest -v                 # wypisuj nazwę każdego testu
uv run pytest -vv -s             # + nieprzechwycony stdout (print, logi)
make tests-without-playwright    # szybki wariant bez testów E2E
```

Reuse kontenerów testowych między uruchomieniami (znacznie szybsze
kolejne biegi):

```bash
PYTEST_TESTCONTAINERS_REUSE=1 uv run pytest
```

## Szybkie uruchomienie wersji deweloperskiej (`run_site`)

Komenda `manage.py run_site` uruchamia kompletny lokalny stack BPP
w **testcontainerach** (PostgreSQL + Redis na losowych portach), więc
można mieć kilka konfiguracji obok siebie bez konfliktów portów.

```bash
# Z baseline.sql (pusta baza demo):
uv run python src/manage.py run_site

# Z dump-em produkcyjnym (autodetect formatu):
uv run python src/manage.py run_site --from-dump ~/backups/bpp.pg_dump
```

Co robi:

1. Startuje PostgreSQL + Redis w kontenerach Docker na losowych portach.
2. Odtwarza dump (`.sql` / `.sql.gz` / `.dump` / `.pg_dump` / `.pgdump`)
   lub baseline (jeśli `--from-dump` nie podany).
3. Wykonuje `migrate --noinput`.
4. Tworzy lub nadpisuje superusera `admin` / `admin` z czyszczeniem
   wymogu zmiany hasła (świeży wpis w `password_policies.PasswordHistory`).
5. Drukuje banner z URL-ami i otwiera przeglądarkę na `/admin/`.
6. Odpala `runserver` na losowym wolnym porcie i blokuje.

`Ctrl-C` zatrzymuje runserver i sprząta kontenery.

Opcje:

| Flaga | Działanie |
|-------|-----------|
| `--from-dump PATH` | Restore z dump-a (autodetect po extension). |
| `--with-celery` | Dodatkowo odpala celery worker. |
| `--no-browser` | Nie otwiera przeglądarki. |
| `--port PORT` | Konkretny port runserver (default: losowy wolny). |
| `--reuse` | Reusuje istniejące named containery (szybszy restart). |

**Wymaganie:** działający Docker daemon. Kontenery są ulotne — żyją
tylko podczas trwania komendy (chyba że `--reuse`).

## Technologie

| | |
|---|---|
| **Backend** | Python 3.10+, Django 4.2, Celery, Django Channels |
| **Baza danych** | PostgreSQL |
| **Cache / broker** | Redis |
| **Frontend** | Foundation CSS, jQuery, HTMX, Select2 |
| **Infrastruktura** | Docker, Nginx, Prometheus, Grafana |

## Zgłaszanie problemów

- **Klienci komercyjni** — portal wsparcia:
  [support.iplweb.pl](https://support.iplweb.pl/)
- **Społeczność** — zgłoszenia na GitHub:
  [github.com/iplweb/bpp/issues](https://github.com/iplweb/bpp/issues)
- **Luki bezpieczeństwa** — *nie* otwieraj publicznego issue. Zob.
  [SECURITY.md](SECURITY.md) — preferowany kanał:
  [GitHub Security Advisory](https://github.com/iplweb/bpp/security/advisories/new).

## Dokumentacja

Dokumentacja dostępna jest na stronie
[iplweb.github.io/bpp](https://iplweb.github.io/bpp/)
(równolegle nadal budowana także na
[bpp.readthedocs.io](https://bpp.readthedocs.io/)).

## Rozwój

Chcesz pomóc w rozwoju projektu? Przeczytaj
[CONTRIBUTING.md](CONTRIBUTING.md).

## Licencja

[MIT](LICENSE)
