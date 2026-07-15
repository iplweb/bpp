Poprawiona stabilność testów przy uruchamianiu współbieżnym (pytest-xdist,
sharding CI): izolowany per-worker ``MEDIA_ROOT`` w tempdirze (zamiast
współdzielonego ``src/media``), poprawna kolejność teardownu fixture'ów
Playwright (TRUNCATE bazy dopiero po zamknięciu przeglądarki), reruny
``@flaky`` działające także dla ``AssertionError``, jednoznaczne flagi
eager Celery, przywrócony per-worker ``KEY_PREFIX`` cache'a constance
oraz czyszczenie cache ``Site`` w testowym serwerze Daphne.
