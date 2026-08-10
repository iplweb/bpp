# Benchmark ORM-a na kopii bazy produkcyjnej (`bench/`)

Harness do mierzenia liczby zapytań i czasu odpowiedzi na **prawdziwych
danych**, przez prawdziwe requesty (`django.test.Client`), a nie na
mikrobenchmarkach. Powstał przy audycie Django 6.1 (*fetch modes*) i służy
dwóm rzeczom:

1. **wykrywaniu N+1** — mierzonemu, nie zgadywanemu,
2. **weryfikacji optymalizacji** — czy spadek liczby zapytań jest realny
   i czy strona nadal zwraca to samo.

## Warunki wstępne

* działający Docker,
* dump bazy produkcyjnej (patrz „Baza" niżej),
* Django >= 6.1 dla `--inwentarz`, `bench_atrybucja.py` i
  `bench_licznik_wywolan.py` (używają *fetch modes*). `--pomiar` działa też
  na 5.2.

## Baza

Stawiamy **własny** kontener PostgreSQL na nietypowym porcie, żeby nie
kolidować z `docker compose up db redis` ani z `run-site`:

```bash
docker run -d --name bpp-bench-pg -p 55432:5432 \
  -e POSTGRES_USER=bpp -e POSTGRES_PASSWORD=password -e POSTGRES_DB=bpp \
  --shm-size=1g iplweb/bpp_dbserver:psql-16.13 \
  -c shared_buffers=1GB -c work_mem=64MB -c maintenance_work_mem=512MB
docker run -d --name bpp-bench-redis -p 55379:6379 redis:7-alpine
```

Dump produkcyjny `db-backup-*.tar.gz` to **format katalogowy**
(`pg_dump -Fd`) zapakowany w tar — NIE `.sql` ani `.dump`, więc
`run-site --from-dump` go nie przyjmie. Rozpakuj i odtwórz przez
`pg_restore`:

```bash
gzip -dc db-backup-20260603-023000.tar.gz | tar -xf -
PGPASSWORD=password pg_restore -h localhost -p 55432 -U bpp -d bpp \
  --no-owner --no-privileges --no-comments -j 6 db-backup-20260603-023000/
```

Dwa błędy `nierozpoznany parametr konfiguracyjny "transaction_timeout"` są
normalne — `pg_restore` 18 emituje GUC z PG 17+, którego PG 16 nie zna.

Potem doprowadź schemat do HEAD (dump bywa starszy niż gałąź):

```bash
DJANGO_SETTINGS_MODULE=django_bpp.settings.bench \
  uv run python src/manage.py migrate --noinput
```

## Dwa warianty konfiguracji — używaj OBU

| moduł settings | `CACHEOPS` | co mierzy |
|---|---|---|
| `django_bpp.settings.bench` | brak reguł (jak `local.py`) | pełną pracę bazy, bez maskowania |
| `django_bpp.settings.bench_prod` | reguły **wczytane z `production.py`** | to, co realnie zobaczy wdrożenie |

To rozróżnienie jest krytyczne, a łatwo je przeoczyć: `local.py` **nie
definiuje `CACHEOPS` wcale**, a produkcja cache'uje `bpp.uczelnia`,
`bpp.jednostka`, `bpp.tytul` i pozostałe słowniki. Pomiar tylko na
`local.py` **zawyża** zysk — liczy jako zapytania do PostgreSQL coś, co na
produkcji jest trafieniem w Redisa. Przy audycie Django 6.1 różnica była
dramatyczna: changelist autorów pokazywał 1102 → 96 zapytań bez cacheops,
a z produkcyjnymi regułami 27 → 27, czyli **zysk zerowy**.

`bench_prod.py` czyta reguły z `production.py` przez AST (bez wykonywania
modułu), żeby nie mierzyć własnej, rozjeżdżającej się kopii.

## Użycie

```bash
# inwentarz N+1 — co i gdzie dociąga się leniwie (Django >= 6.1)
uv run python bench/bench_orm.py --inwentarz

# pomiar: liczba zapytań + czas, mediana z N przebiegów
DJANGO_SETTINGS_MODULE=django_bpp.settings.bench_prod \
  uv run python bench/bench_orm.py --pomiar --powtorzenia 25

# sufit wygranej z FETCH_PEERS włączonym globalnie (Django >= 6.1)
uv run python bench/bench_orm.py --pomiar --tryb peers --powtorzenia 25

# dowód, że FETCH_PEERS nie zmienia wyniku (porównanie bajt w bajt)
uv run python bench/bench_rownowaznosc.py

# rozbicie pobrań JEDNEGO pola na miejsca wywołania
uv run python bench/bench_atrybucja.py Jednostka.uczelnia "admin: autor (changelist)"

# licznik budów ChangeList / konsumpcji generatora filtra
uv run python bench/bench_licznik_wywolan.py
```

**Przy każdej zmianie wersji Django wyczyść cacheops**, bo pikluje
instancje modeli i 6.1 czytające wpisy zapisane przez 5.2 daje
`RuntimeWarning` oraz nieważny pomiar:

```bash
docker exec bpp-bench-redis redis-cli -n 7 FLUSHDB
```

## Jak czytać wyniki (i jak nie dać się oszukać)

**Liczby zapytań są dokładne i powtarzalne.** Na nich opieraj wnioski.

**Czasy są wiarygodne tylko na cichym hoście.** Harness oznacza flagą
`SZUM` każdy pomiar, w którym odchylenie standardowe przekracza 10%
mediany — taki wynik jest szumem, nie pomiarem. Na maszynie, gdzie równolegle
biegną testy albo inne stacki, prawie wszystko dostanie tę flagę.

**Scenariusz kontrolny.** `admin: źródło (changelist)` nie był dotykany
żadną z dotychczasowych optymalizacji i ma stale 16 zapytań. Jego rozrzut
między przebiegami to **zmierzona podłoga szumu hosta**: jeśli „poprawiony"
scenariusz zmienił się mniej niż kontrolny, różnica nie jest realna. Przy
audycie ten kontroler pokazał skok 320 → 420 ms na niezmienionej ścieżce
kodu — i dzięki temu od razu było widać, że cały przebieg jest do wyrzucenia.

**Cacheops ukrywa N+1 przed licznikiem zapytań, ale nie przed zegarem.**
Podstrona jednostki miała 10 zapytań przed i po `FETCH_PEERS`, a czas spadł
77 → 54 ms: 109 pobrań `Autor.tytul` było trafieniami w Redisa, więc
licznik SQL ich nie widział. Jeśli liczba zapytań się nie zmienia, a czas
tak — szukaj round-tripów do cache'u.

## Ograniczenia

* pojedyncze żądania sekwencyjne, bez współbieżności — nie mierzy
  zachowania pod obciążeniem ani rywalizacji o połączenia,
* `CACHES["default"]` to `DummyCache` w obu wariantach, więc własny cache
  BPP (`PaginatorZeZliczeniemZCache`, `cache_publiczny`) nie maskuje pracy
  bazy; na produkcji część stron jest dodatkowo cache'owana, co jeszcze
  zmniejsza realny wpływ optymalizacji,
* `--tryb peers` podstawia `DEFAULT_FETCH_MODE` globalnie, czyli mierzy
  SUFIT wygranej, a nie stan produkcyjny (tam `FETCH_PEERS` jest włączony
  tylko w `BaseBppAdminMixin`).
