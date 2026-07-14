# Pakiety klienckie PBN

Kod integracji jest rozwijany w monorepo jako dwa pakiety `uv workspace`:

| Dystrybucja | Import Pythona | Odpowiedzialność |
| --- | --- | --- |
| `pbn-client` | `pbn_client` | HTTP, uwierzytelnianie i protokół API PBN |
| `django-pbn-client` | `django_pbn_client` | abstrakcyjne modele i zapis stron PBN |

BPP zależy od obu dystrybucji. `django-pbn-client` zależy dodatkowo od
`pbn-client`. Istniejąca aplikacja `pbn_api`, jej etykieta Django, konkretne
modele i migracje pozostają w BPP. Moduł `pbn_api.models.base` jest warstwą
zgodności, która eksportuje klasy bazowe z nowego pakietu.

Pakiety znajdują się odpowiednio w `packages/pbn-client` i
`packages/django-pbn-client`. Zwykłe `uv sync --no-install-project` pomija
jedynie główny, niepublikowalny projekt BPP; nadal instaluje członków workspace.
Testy pakietów są zbierane razem z testami z `src`.

## Ograniczenie pierwszego etapu

`pbn-client` jest warstwą transportową i nie może zależeć od modeli BPP ani od
`pbn_api`. `django-pbn-client` udostępnia abstrakcyjne klasy bazowe oraz
generyczne usługi pobierania stron i zapisu. Nie dostarcza jeszcze zestawu
konkretnych modeli lustrzanych, który można dodać do `INSTALLED_APPS` bez kodu
projektu korzystającego z biblioteki.

W pierwszym etapie konkretne modele, ich relacje do BPP oraz historia migracji
pozostają w `pbn_api`. Orkiestracja importu, dopasowywanie rekordów, Celery i
interfejs pobierania również pozostają po stronie BPP. Późniejsze wydzielenie
konkretnych modeli wymaga zaprojektowania konfigurowalnych relacji i osobnej
strategii migracji; nie należy przenosić istniejących migracji ani zmieniać
etykiety aplikacji przy okazji tego wydzielenia.

Pobieranie równoległe domyślnie używa wątków. Opcjonalny tryb
`method="processes"` korzysta z POSIX-owego mechanizmu `fork`, więc nie jest
dostępny w systemie Windows.

## Budowanie i kontenery

Każdy etap obrazu, który wykonuje `uv sync`, kopiuje wcześniej katalog
`packages/` i instaluje członków workspace nieedytowalnie. Dzięki temu venv
kopiowany między etapami nie zawiera odwołań do ścieżek z etapu budującego.
Zmiana kodu pakietu wymaga zatem ponownego zbudowania obrazu developerskiego.

Pakiety można sprawdzić niezależnie:

```bash
uv run pytest packages/pbn-client/tests
uv run pytest packages/django-pbn-client/tests
uv build --package pbn-client
uv build --package django-pbn-client
```
