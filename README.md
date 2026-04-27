<p align="center">
  <img src="https://github.com/iplweb/bpp/raw/dev/src/bpp/static/bpp/images/logo_bpp.png" width="480" alt="Logo BPP">
</p>

<h1 align="center">BPP — Bibliografia Publikacji Pracowników</h1>

<p align="center">
  <a href="https://github.com/iplweb/bpp/actions/workflows/tests.yml"><img src="https://github.com/iplweb/bpp/actions/workflows/tests.yml/badge.svg?branch=dev" alt="Testy"></a>
  <a href="https://github.com/iplweb/bpp/actions/workflows/build-docker-images.yml"><img src="https://github.com/iplweb/bpp/actions/workflows/build-docker-images.yml/badge.svg?branch=master" alt="Docker - oficjalne obrazy"></a>
  <a href="http://bpp.readthedocs.io/pl/latest/?badge=latest"><img src="https://readthedocs.org/projects/bpp/badge/?version=latest" alt="Dokumentacja"></a>
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
- Integracja z Polską Bibliografią Naukową (PBN)
- Integracja z ORCID i CrossRef
- Raporty ewaluacyjne i analiza slotów
- Ranking autorów i punktacja publikacji
- Klasyfikacja i śledzenie Open Access
- Import i eksport danych z zewnętrznych systemów
- System zgłaszania publikacji przez pracowników
- Powiadomienia w czasie rzeczywistym

## Wymagania systemowe

- PostgreSQL
- Redis
- RabbitMQ
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
> oraz obrazy Dockera dla testcontainers (PostgreSQL, Redis, RabbitMQ).
> Łącznie kilkaset MB do kilku GB transferu sieciowego. Pod każdym krokiem
> podany jest sposób, jak włączyć szczegółowe logowanie postępu.

### 1. Sklonuj repozytorium

```bash
git clone https://github.com/iplweb/bpp.git
cd bpp
```

### 2. Zainstaluj zależności Pythona i Playwright

```bash
uv sync --extra=dev
uv run playwright install
sudo playwright install-deps
```

`uv sync --extra=dev` instaluje pakiety potrzebne do pracy
i testów (pytest, pytest-django, model-bakery, ruff, pre-commit, …).
`uv run playwright install` pobiera przeglądarki używane w testach E2E
(~500 MB). `sudo playwright install-deps` doinstalowuje systemowe
biblioteki, których wymagają te przeglądarki (libnss3, libatk, libgtk-3,
…) — wymaga sudo, bo używa `apt`.

Aby uzyskać dodatkowe logowanie postępu:

- `uv sync --extra=dev -v` — verbose output uv
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

Pytest startuje **własne** kontenery Docker (PostgreSQL, Redis, RabbitMQ)
przez plugin `testcontainers_bpp` — przy pierwszym uruchomieniu pobiera
obrazy z Docker Hub (kolejne kilkaset MB). Wymagany jest działający
**Docker daemon**.

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
BPP_TESTCONTAINERS_REUSE=1 uv run pytest
```

### Skrót: `make prepare-developer-machine-linux`

Część kroku 2 (zależności systemowe + `uv sync --all-extras`)
automatyzuje cel:

```bash
make prepare-developer-machine-linux
```

Instaluje przez `apt` pakiety `yarnpkg`, `python3-dev`, `libpq-dev`,
`libcairo2-dev`, `libpango1.0-dev`, `libgdk-pixbuf2.0-dev`, `libffi-dev`,
`libgirepository1.0-dev`, `libgtk-3-dev`, a następnie woła
`uv sync --all-extras`. Po nim nadal trzeba ręcznie wywołać
`uv run playwright install` oraz `sudo playwright install-deps`.

## Technologie

| | |
|---|---|
| **Backend** | Python 3.10+, Django 4.2, Celery, Django Channels |
| **Baza danych** | PostgreSQL |
| **Cache / broker** | Redis, RabbitMQ |
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
[bpp.readthedocs.io](https://bpp.readthedocs.io/).

## Rozwój

Chcesz pomóc w rozwoju projektu? Przeczytaj
[CONTRIBUTING.md](CONTRIBUTING.md).

## Licencja

[MIT](LICENSE)
