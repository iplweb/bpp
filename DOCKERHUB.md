<p align="center">
  <img src="https://github.com/iplweb/bpp/raw/dev/src/bpp/static/bpp/images/logo_bpp.png" width="480" alt="Logo BPP">
</p>

<h1 align="center">BPP — Bibliografia Publikacji Pracowników</h1>

<p align="center">
  <b>Wsparcie komercyjne zapewnia</b><br><br>
  <a href="https://bpp.iplweb.pl"><img src="https://www.iplweb.pl/images/ipl-logo-large.png" width="150" alt="IPL Web"></a>
</p>

<p align="center">
  <a href="https://github.com/iplweb/bpp">Source on GitHub</a> •
  <a href="https://www.iplweb.pl">iplweb.pl</a> •
  <a href="https://bpp.iplweb.pl">bpp.iplweb.pl</a> •
  <a href="https://iplweb.github.io/bpp/">Dokumentacja</a>
</p>

---

## Co to jest

**BPP (Bibliografia Publikacji Pracowników)** — otwartoźródłowy (MIT) system
informatyczny do katalogowania bibliografii publikacji pracowników naukowych.
Używany przez biblioteki naukowe i uniwersyteckie w Polsce do zarządzania
dorobkiem publikacyjnym, ewaluacji i integracji z PBN / ORCID / CrossRef.

Ten obraz jest **częścią stacku mikroserwisów BPP** — nie jest samodzielną
aplikacją. Pełne wdrożenie (PostgreSQL, Redis, nginx, wszystkie serwisy)
opisane w [iplweb/bpp-deploy](https://github.com/iplweb/bpp-deploy).

## Obrazy stacku BPP

| Obraz | Rola |
|---|---|
| [`iplweb/bpp_base`](https://hub.docker.com/r/iplweb/bpp_base) | Base image — Django, Python deps, build-time zasoby (JS/CSS) dla pozostałych obrazów. |
| [`iplweb/bpp_appserver`](https://hub.docker.com/r/iplweb/bpp_appserver) | Web (Django + Daphne) — główny backend HTTP/WebSocket. |
| [`iplweb/bpp_workerserver`](https://hub.docker.com/r/iplweb/bpp_workerserver) | Celery worker — zadania asynchroniczne (import, export, PBN). |
| [`iplweb/bpp_beatserver`](https://hub.docker.com/r/iplweb/bpp_beatserver) | Celery beat — scheduler zadań periodycznych. |
| [`iplweb/bpp_authserver`](https://hub.docker.com/r/iplweb/bpp_authserver) | Serwer autentykacji (SSO). |
| [`iplweb/bpp_denorm_queue`](https://hub.docker.com/r/iplweb/bpp_denorm_queue) | Kolejka denormalizacji danych. |
| [`iplweb/bpp_dbserver`](https://hub.docker.com/r/iplweb/bpp_dbserver) | PostgreSQL + plpython3u + ICU pl-PL + autotune. Wydzielone repo: [iplweb/bpp-dbserver](https://github.com/iplweb/bpp-dbserver). |

## Wdrożenie

**Produkcja / staging:** sklonuj [iplweb/bpp-deploy](https://github.com/iplweb/bpp-deploy) —
tam znajdziesz `docker-compose.yml`, `.env.example`, instrukcje backupu
i konfigurację nginx. Repo publikacyjne zarządza wersją (pin na konkretny tag)
i orkiestracją wszystkich serwisów.

**Lokalnie (developerskie):** repo [iplweb/bpp](https://github.com/iplweb/bpp)
zawiera `Makefile` z targetami do lokalnego build-a i uruchomienia stacku.

**Do wersji demo — skontaktuj się pod adresem e-mail michal.dtz@gmail.com.**

## Tagi

- **`<YYMM.N>`** (np. `202604.1234`) — konkretna wersja, zalecana dla produkcji.
- **`latest`** — najnowsze wydanie z `master`. OK dla staging/dev.
- **`<branch-name>`** (np. `feature-foo`) — obrazy z feature branchy, dla testów.

Wszystkie obrazy stacku są taggowane **synchronicznie** — `iplweb/bpp_appserver:202604.1234`
współpracuje tylko z `iplweb/bpp_workerserver:202604.1234` tej samej wersji.
Nie mieszaj tagów między serwisami.

## Główne funkcje BPP

- Zarządzanie bibliografią publikacji pracowników naukowych
- Integracja z **Polską Bibliografią Naukową (PBN)**
- Integracja z **ORCID** i **CrossRef**
- Raporty ewaluacyjne i analiza slotów
- Ranking autorów i punktacja publikacji
- Klasyfikacja i śledzenie **Open Access**
- Import/eksport danych z zewnętrznych systemów
- System zgłaszania publikacji przez pracowników
- Powiadomienia w czasie rzeczywistym (Django Channels)

## Wymagania stacku

- PostgreSQL (użyj [`iplweb/bpp_dbserver`](https://hub.docker.com/r/iplweb/bpp_dbserver) — ma `plpython3u`, ICU `pl-PL` i autotune)
- Redis (cache / Celery broker / Channels)
- nginx (reverse proxy)

Pełna lista z wersjami — [bpp-deploy/docker-compose.yml](https://github.com/iplweb/bpp-deploy/blob/main/docker-compose.yml).

## Technologie

| | |
|---|---|
| **Backend** | Python 3.12+, Django 4.2, Celery, Django Channels |
| **Baza danych** | PostgreSQL 16/17/18 (via `iplweb/bpp_dbserver`) |
| **Cache / broker** | Redis |
| **Frontend** | Foundation CSS, jQuery, HTMX, Select2 |
| **Infrastruktura** | Docker, nginx, Prometheus, Grafana |

## Zgłaszanie problemów

- **Klienci komercyjni** — portal wsparcia: [support.iplweb.pl](https://support.iplweb.pl/)
- **Społeczność** — GitHub Issues: [github.com/iplweb/bpp/issues](https://github.com/iplweb/bpp/issues)

## Źródła

- 💻 **Kod monorepo**: [github.com/iplweb/bpp](https://github.com/iplweb/bpp)
- 🚀 **Wdrożenie produkcyjne**: [github.com/iplweb/bpp-deploy](https://github.com/iplweb/bpp-deploy)
- 🐘 **dbserver (wydzielony)**: [github.com/iplweb/bpp-dbserver](https://github.com/iplweb/bpp-dbserver)
- 📚 **Dokumentacja**: [iplweb.github.io/bpp](https://iplweb.github.io/bpp/)
- 🌐 **Strona projektu / demo**: [bpp.iplweb.pl](https://bpp.iplweb.pl)
- 💼 **Wsparcie komercyjne**: [iplweb.pl](https://www.iplweb.pl)

## Licencja

[MIT](https://github.com/iplweb/bpp/blob/dev/LICENSE) — Copyright © 2017–2026 Michał Pasternak &lt;michal.dtz@gmail.com&gt;.
