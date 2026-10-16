Sesja testów bez ani jednego testu korzystającego z bazy danych wywalała
się na gałęzi soft-delete autorstwa błędem ``UndefinedColumn: kolumna
deleted_at nie istnieje`` przy instalacji triggerów denorm, gdy testowa
baza pochodziła sprzed migracji dodającej tę kolumnę (np. reużyty
kontener testowy ze starym schematem). Rozpoznajemy teraz ten jeden,
konkretny przypadek i pomijamy instalację triggerów z czytelnym
ostrzeżeniem zamiast wywalać całą sesję pytest.
