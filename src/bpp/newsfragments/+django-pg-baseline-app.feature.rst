Logika szybkiego bootstrapu bazy testowej z ``pg_dump`` (dotychczas
rozproszona po ``baseline/``, ``src/conftest.py``, ``Makefile``,
``docker-compose.baseline.yml`` i entrypoincie kontenera) została
wyodrębniona do reusable Django app ``django_pg_baseline`` w
``src/django_pg_baseline/``.

Pakiet udostępnia cztery komendy zarządzania: ``baseline_rebuild``
(regeneruje dump przez ``testcontainers``, bez potrzeby oddzielnego
``docker-compose.baseline.yml``), ``baseline_load`` (ładuje dump do
wskazanej bazy, no-op gdy baza nie jest pusta), ``baseline_check``
(gate CI sprawdzający deltę migracji) oraz ``baseline_info``
(czytelny raport o stanie baseline).

Monkey-patch na ``_create_test_db``, wcześniej wklejony inline w
``src/conftest.py``, jest teraz instalowany automatycznie z
``AppConfig.ready()`` gdy pakiet jest w ``INSTALLED_APPS``.

Katalog z dumpem został przeniesiony z ``baseline/`` do
``src/baseline-sql/`` — ``baseline.sql`` i ``baseline.meta.json``
dalej żyją w repo, ale jako wyraźny data sidecar obok kodu pakietu.
Konfiguracja w ``settings.PG_BASELINE`` została skrócona z ~25 linii
do kilku kluczy; defaulty (lista argumentów ``pg_dump``, zamrażane
kolumny timestampów, alias bazy, próg freshness) żyją teraz w samym
pakiecie, a projekt-konsument ustawia tylko ``BASELINE_DIR`` plus
ewentualne nadpisania.

Zależność ``testcontainers[postgres]`` jest opcjonalna
(``uv sync --extra baseline-rebuild``) — wymagana tylko dla
``baseline_rebuild``, pozostałe komendy jej nie potrzebują.
