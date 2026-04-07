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

Instrukcja instalacji i wdrożenia dostępna jest na stronie
[bpp.iplweb.pl/zrodla](https://bpp.iplweb.pl/zrodla) oraz w repozytorium
**[bpp-deploy](https://github.com/iplweb/bpp-deploy)**.

## Wersja demo

Live-demo serwisu dostępne jest na żądanie — prosimy o kontakt
pod adresem e-mail michal.dtz@gmail.com.

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

## Dokumentacja

Dokumentacja dostępna jest na stronie
[bpp.readthedocs.io](https://bpp.readthedocs.io/).

## Rozwój

Chcesz pomóc w rozwoju projektu? Przeczytaj
[CONTRIBUTING.md](CONTRIBUTING.md).

## Licencja

[MIT](LICENSE)
