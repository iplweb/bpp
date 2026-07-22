# Pakiety klienckie PBN

Kod integracji z PBN jest wydzielony do **dwóch samodzielnych pakietów**
publikowanych na PyPI (repozytoria pod `github.com/iplweb/`):

| Dystrybucja (PyPI) | Import Pythona | Repozytorium | Odpowiedzialność |
| --- | --- | --- | --- |
| `pbn-client` | `pbn_client` | [iplweb/pbn-client](https://github.com/iplweb/pbn-client) | HTTP, uwierzytelnianie i protokół API PBN (niezależne od Django) |
| `django-pbn-client` | `django_pbn_client` | [iplweb/django-pbn-client](https://github.com/iplweb/django-pbn-client) | abstrakcyjne modele Django i pobieranie/zapis stron PBN |

BPP zależy od obu dystrybucji jak od każdej innej zależności z PyPI
(`pyproject.toml`, sekcja `[project.dependencies]`). `django-pbn-client`
zależy dodatkowo od `pbn-client`. Istniejąca aplikacja `pbn_api`, jej etykieta
Django, konkretne modele i migracje pozostają w BPP. Moduł `pbn_api.models.base`
oraz część `pbn_api.exceptions`/`pbn_api.const` to cienkie warstwy zgodności
re-eksportujące klasy z nowych pakietów.

**W repozytorium BPP nie ma już katalogu `packages/` ani konfiguracji
`uv workspace`.** Zmiana kodu klienta = PR do właściwego repozytorium pakietu →
nowe wydanie na PyPI (przez GitHub Release + Trusted Publishing) → bump wersji
zależności w BPP.

## Podział odpowiedzialności

`pbn-client` jest warstwą protokołu i nie może zależeć od modeli BPP ani od
`pbn_api`. `django-pbn-client` udostępnia abstrakcyjne klasy bazowe oraz
generyczne usługi pobierania stron i zapisu (m.in. `download_to_model`,
`get_or_download`). **Nie** dostarcza konkretnych modeli lustrzanych — te,
ich relacje do BPP oraz historia migracji pozostają w `pbn_api`. Orkiestracja
importu, dopasowywanie rekordów, Celery i interfejs pobierania również
pozostają po stronie BPP.

Późniejsze wydzielenie konkretnych modeli wymagałoby zaprojektowania
konfigurowalnych relacji i osobnej strategii migracji; nie należy przenosić
istniejących migracji ani zmieniać etykiety aplikacji.

Pobieranie równoległe domyślnie używa wątków. Opcjonalny tryb
`method="processes"` korzysta z POSIX-owego `fork`, więc nie jest dostępny na
Windows.

## Aktualizacja wersji pakietu w BPP

```bash
# po wydaniu nowej wersji pakietu na PyPI:
uv add "pbn-client>=0.2,<0.3"           # lub edycja pyproject.toml
uv sync --refresh-package pbn-client    # --refresh gdy index uv jest zcache'owany
uv run python src/manage.py check
uv run python src/manage.py makemigrations --check --dry-run   # brak dryfu pbn
```

## Wydawanie nowej wersji pakietu

W repozytorium danego pakietu (nie w BPP):

1. Bump `version` w `pyproject.toml`, merge do `main`.
2. Utwórz GitHub Release z tagiem `vX.Y.Z` — workflow `release.yml` publikuje na
   PyPI przez **Trusted Publishing** (OIDC, bez tokena).
3. Zbump zależność w BPP (sekcja wyżej).
