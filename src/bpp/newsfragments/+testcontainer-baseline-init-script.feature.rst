Uruchamianie testów na świeżej maszynie nie wymaga już hostowego klienta
``psql``. Plugin ``testcontainers_bpp`` mountuje ``baseline.sql`` jako
``/docker-entrypoint-initdb.d/01-baseline.sql`` w kontenerze Postgresa,
więc wbudowany entrypoint obrazu sam ładuje dump przy starcie — wewnątrz
kontenera, bez udziału hosta. Plugin ustawia też
``DJANGO_BPP_TEST_TEMPLATE=bpp``, dzięki czemu Django tworzy ``test_bpp``
przez natywne ``CREATE DATABASE … WITH TEMPLATE bpp`` (instant clone w
silniku), zamiast ponownie odgrywać dump przez ``psql``. Hostowy ``psql``
pozostaje wymagany tylko dla ``manage.py baseline_load`` i scenariusza
``--no-testcontainers`` (gdzie usługi dostarcza docker-compose).

Konwencja lokalizacji baseline: ``src/baseline-sql/baseline.sql``;
override przez ``BPP_BASELINE_SQL_PATH``. Patch w
``django_pg_baseline.patches`` dodatkowo zamyka połączenie Django i
ubija pozostałe sesje na bazie-szablonie (``pg_terminate_backend``)
przed CREATE, żeby Postgres pozwolił na clone.
