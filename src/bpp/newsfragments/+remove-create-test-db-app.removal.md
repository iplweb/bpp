Usunięto martwą aplikację ``create_test_db`` wraz z jej jedynym
poleceniem ``manage.py create_test_db``. Komenda wykorzystywała
sztuczkę z ``manage.py test --keepdb`` do utworzenia bazy testowej
i nie była już używana przez CI ani lokalny workflow. Aktualnie
funkcjonalność pokrywają ``pytest-testcontainers`` (testy
integracyjne na ulotnym kontenerze PostgreSQL) oraz
``run-site --from-dump`` (odtworzenie bazy z dumpa).
